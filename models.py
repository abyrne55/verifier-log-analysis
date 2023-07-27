"""Data models for verifier log analysis"""
import json
from datetime import datetime
from enum import Enum
from typing import Optional

from util import csv_bool_to_bool, is_nully_str, is_valid_url


class OCMState(Enum):
    """
    States in which an OCM cluster could be, according to
    https://gitlab.cee.redhat.com/service/uhc-clusters-service/-/blob/master/pkg/models/clusters.go
    """

    VALIDATING = "validating"
    WAITING = "waiting"
    PENDING = "pending"
    INSTALLING = "installing"
    READY = "ready"
    ERROR = "error"
    UNINSTALLING = "uninstalling"
    UNKNOWN = "unknown"
    POWERING_DOWN = "powering_down"
    RESUMING = "resuming"
    HIBERNATING = "hibernating"

    def is_transient(self):
        """
        Returns True if representing a "non-steady state" (e.g., installing, validating)
        """
        return self not in [
            self.READY,
            self.ERROR,
            self.UNINSTALLING,
            self.HIBERNATING,
        ]

    def __repr__(self):
        return f"<{self.__class__.__name__}.{self.name}>"


class InFlightState(Enum):
    """
    States in which an in-flight check could be, according to
    https://gitlab.cee.redhat.com/service/uhc-clusters-service/-/blob/master/pkg/models/inflight_checks.go
    """

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"

    def __repr__(self):
        return f"<{self.__class__.__name__}.{self.name}>"


class ClusterVerifierRecord:
    """Represents a single row in the CSV"""

    def __init__(
        self,
        timestamp: datetime,
        cid: str,
        cname: Optional[str],
        ocm_state: Optional[OCMState],
        ocm_inflight_states: Optional[list[str]],
        found_verifier_s3_logs: Optional[bool],
        found_all_tests_passed: Optional[bool],
        found_egress_failures: Optional[bool],
        log_download_url: str,
    ):
        self.timestamp = timestamp
        self.cid = cid
        self.cname = cname
        self.ocm_state = ocm_state
        self.ocm_inflight_states = ocm_inflight_states
        self.found_verifier_s3_logs = found_verifier_s3_logs
        self.found_all_tests_passed = found_all_tests_passed
        self.found_egress_failures = found_egress_failures
        self.log_download_url = log_download_url

    def __gt__(self, other):
        return self.timestamp > other.timestamp

    def __lt__(self, other):
        return self.timestamp < other.timestamp

    def __repr__(self):
        in_flight_str = ""
        if self.ocm_inflight_states is not None:
            in_flight_str = (
                f"[{''.join(repr(s)+',' for s in self.ocm_inflight_states)}]"
            )
        return (
            f"<CVR.{self.cid if self.cname is None else self.cname} "
            f"{'' if self.ocm_state is None else repr(self.ocm_state)} "
            f"{in_flight_str}>"
        )

    @classmethod
    def from_dict(cls, in_dict: dict[str, str]):
        """Create an instance of this class from a dictionary produced by csv.DictReader"""

        # Mandatory Fields
        timestamp = datetime.fromisoformat(in_dict["timestamp"].replace("Z", "+00:00"))
        cid = in_dict["cid"].strip()
        if is_nully_str(cid):
            raise ValueError(
                "Cannot create ClusterVerifierRecord without cluster ID (cid)"
            )

        # Optional Fields
        try:
            cname = None if is_nully_str(in_dict["cname"]) else in_dict["cname"].strip()
            found_verifier_s3_logs = csv_bool_to_bool(in_dict["found_verifier_s3_logs"])
            found_all_tests_passed = csv_bool_to_bool(in_dict["found_all_tests_passed"])
            found_egress_failures = csv_bool_to_bool(in_dict["found_egress_failures"])
            ocm_state_str = in_dict["ocm_state"].lower().strip()
            ocm_inflight_states_str = in_dict["ocm_inflight_states"].strip()
        except AttributeError as exc:
            # .strip()/.lower() will raise AttributeError for non-str types, but we
            # consider this a ValueError
            raise ValueError("Non-str-typed keys passed to from_dict()") from exc

        # Finish processing "strictly typed" fields (these will raise their own exceptions)
        ocm_state = None
        if not is_nully_str(ocm_state_str):
            ocm_state = OCMState(ocm_state_str)

        ocm_inflight_states = None
        if not is_nully_str(ocm_inflight_states_str):
            ocm_inflight_states = list(
                InFlightState(s) for s in json.loads(in_dict["ocm_inflight_states"])
            )

        log_download_url = None
        if is_valid_url(in_dict["log_download_url"]):
            log_download_url = in_dict["log_download_url"]

        return cls(
            timestamp,
            cid,
            cname,
            ocm_state,
            ocm_inflight_states,
            found_verifier_s3_logs,
            found_all_tests_passed,
            found_egress_failures,
            log_download_url,
        )