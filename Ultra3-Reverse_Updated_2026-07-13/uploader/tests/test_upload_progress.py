from ultra3_uploader.upload_progress import make_progress
from ultra3_uploader.upload_state import UploadState


def test_progress_uses_file_bytes_only() -> None:
    progress = make_progress(
        packets_sent=2,
        total_packets=4,
        bytes_sent=460,
        total_bytes=920,
        elapsed_seconds=2.0,
        current_sequence=1,
        state=UploadState.SENDING_C9,
    )
    assert progress.current_packet == 2
    assert progress.percent == 50.0
    assert progress.effective_bytes_per_second == 230.0
    assert progress.estimated_remaining_seconds == 2.0


def test_progress_reaches_exactly_100_percent() -> None:
    progress = make_progress(
        packets_sent=3875,
        total_packets=3875,
        bytes_sent=891180,
        total_bytes=891180,
        elapsed_seconds=174.33,
        current_sequence=3874,
        state=UploadState.SENDING_C9,
    )
    assert progress.percent == 100.0
    assert progress.estimated_remaining_seconds == 0.0

