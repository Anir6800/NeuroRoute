from app.services.research_summary import summarize_research


def test_summary_reports_only_the_recorded_delta_and_uncertainty() -> None:
    summary = summarize_research(
        {"mean_delay_ms": 8.0, "loss_probability": 0.02, "sample_count": 5},
        {"mean_delay_ms": 10.0, "loss_probability": 0.03, "sample_count": 5},
    )
    assert summary["observations"] == [
        "Recorded mean delay: candidate 8.000 ms; baseline 10.000 ms; delta -2.000 ms.",
        "Recorded loss probability: candidate 2.000 percentage points; baseline 3.000 percentage points; delta -1.000 percentage points.",
    ]
    assert summary["limitations"] == [
        "Simulated result only; it is not a network measurement.",
        "Uncertainty: 5 candidate and 5 baseline samples; no confidence interval was recorded.",
    ]


def test_summary_refuses_a_claim_when_comparison_data_is_missing() -> None:
    summary = summarize_research({"mean_delay_ms": 8.0})
    assert summary["observations"] == []
    assert summary["limitations"] == [
        "Simulated result only; it is not a network measurement.",
        "No paired baseline outcome metrics were recorded, so no comparative claim is made.",
        "Sample counts and confidence intervals were not recorded; uncertainty cannot be quantified.",
    ]
