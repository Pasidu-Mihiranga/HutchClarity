"""AU02 integration of DATA01 through the existing mask-first service."""

from clarity.integration.drivers.mock.synthetic_dataset import generate_synthetic_dataset
from clarity.modules.autopsy.public import AutopsyService, BatchComplaint


def test_data01_ingests_through_mask_first_service_with_honest_diagnostics():
    dataset = generate_synthetic_dataset(count=190)
    service = AutopsyService()
    intakes = service.ingest(
        BatchComplaint(row.complaint_id, row.text, row.channel) for row in dataset.complaints
    )
    assert all(item.stored for item in intakes)
    report = service.rerun()
    workspace = service.workspace()
    assert report.clusters
    assert workspace["complaint_count"] == 190
    assert workspace["synthetic"] is True
    assert workspace["clustering_method"] == "TrigramSimilarity"
    assert "not semantic embedding" in workspace["clustering_disclosure"]
    assert all(item["hypothesis"] for item in workspace["clusters"])
    assert all(item["trend_label"] == "Synthetic trend" for item in workspace["clusters"])
    assert all(item["representative_masked_complaints"] for item in workspace["clusters"])


def test_dataset_redelivery_does_not_inflate_complaint_count():
    rows = generate_synthetic_dataset(count=40).complaints
    service = AutopsyService()
    batch = [BatchComplaint(row.complaint_id, row.text, row.channel) for row in rows]
    service.ingest(batch)
    service.ingest(batch)
    service.rerun()
    assert service.workspace()["complaint_count"] == 40
