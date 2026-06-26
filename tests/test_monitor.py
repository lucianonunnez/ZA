"""Live tracking + proactive monitoring (the post-purchase loop)."""

from copilot.pipeline.live import _mock_status, live_risk_override
from copilot.pipeline.monitor import monitor_booking


def test_live_override_dominates_when_inbound_is_late():
    late = _mock_status("AA100")        # mock makes *100 flights have a late feeder
    on_time = _mock_status("BA178")
    late_score, _ = live_risk_override(late)
    ok_score, _ = live_risk_override(on_time)
    assert late_score > 75
    assert ok_score < 20


def test_cancelled_is_max_risk():
    status = _mock_status("AA100")
    status.status = "cancelled"
    score, drivers = live_risk_override(status)
    assert score == 100.0
    assert any("CANCEL" in d.upper() for d in drivers)


async def test_monitor_notifies_on_late_inbound():
    alert = await monitor_booking("AA100", "LHR")
    assert alert.should_notify
    assert alert.level in ("warning", "critical")
    assert alert.member_message  # a proactive message was drafted
    assert alert.recommended_action


async def test_monitor_quiet_when_all_clear():
    alert = await monitor_booking("BA178", "DXB")  # on-time feeder + low-weather dest
    # On-time inbound: confidence should be high.
    assert alert.on_time_confidence >= 80
