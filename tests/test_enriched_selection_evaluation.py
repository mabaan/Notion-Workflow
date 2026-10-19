from dataclasses import asdict
import json

from scripts.evaluate_article_classifier import FIXTURE, baseline
from scripts.evaluate_enriched_selection import evaluate_paths, retained_sets
from research_automation.models.article import EnrichedArticle
from research_automation.pipeline.candidate_ranking import calculate_queue_score


def case(key="oct16-veal", *, region="Egypt"):
    snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot["articles"] = [row for row in snapshot["articles"] if row["article_id"] == key]
    old = baseline(snapshot)
    experiments = {"luna-100": {"outcomes": [dict(article_id=key, error=None, classification=dict(
        decision="Relevant", relevance_score=5, assigned_region=region))]}}
    return snapshot, old, experiments


def enrichment(score, significance=3):
    return dict(enrichment=asdict(EnrichedArticle("Mock evidence summary", "Mock mission reason", score,
                                                editorial_significance=significance)), error=None)


def test_both_paths_use_shared_luna_enrichment_score_and_unchanged_queue_weights():
    snapshot, old, experiments = case()
    paths = evaluate_paths(snapshot, old, experiments, {"oct16-veal": enrichment(4)})["paths"]
    assert paths["deterministic"]["qualified_ids"] == paths["luna-100"]["qualified_ids"] == ["oct16-veal"]
    assert paths["deterministic"]["rows"]["oct16-veal"]["queue_score"] == calculate_queue_score(4, 6, 3)
    # Classifier score 5 does not replace enrichment score 4.
    assert paths["luna-100"]["rows"]["oct16-veal"]["enrichment_relevance"] == 4


def test_classifier_relevance_does_not_override_failed_enrichment_threshold():
    snapshot, old, experiments = case()
    paths = evaluate_paths(snapshot, old, experiments, {"oct16-veal": enrichment(3)})["paths"]
    for path in paths.values():
        assert path["qualified_ids"] == path["final_winner_ids"] == []
        assert path["rows"]["oct16-veal"]["required_relevance"] == 4


def test_unregistered_articles_still_require_five():
    snapshot, old, experiments = case("oct16-gerd")
    paths = evaluate_paths(snapshot, old, experiments, {"oct16-gerd": enrichment(4)})["paths"]
    for path in paths.values():
        assert path["qualified_ids"] == []
        assert path["rows"]["oct16-gerd"]["required_relevance"] == 5


def test_unclear_classifier_region_keeps_qualified_article_pending_without_quota_guess():
    snapshot, old, experiments = case("oct16-iraq", region="Out of Scope/Unclear")
    paths = evaluate_paths(snapshot, old, experiments, {"oct16-iraq": enrichment(5)})["paths"]
    assert paths["luna-100"]["qualified_ids"] == ["oct16-iraq"]
    assert paths["luna-100"]["final_winner_ids"] == []
    assert paths["deterministic"]["final_winner_ids"] == ["oct16-iraq"]
    assert "geography unresolved" in paths["luna-100"]["rows"]["oct16-iraq"]["status"]


def test_failed_enrichment_is_operational_uncertainty_not_editorial_rejection():
    snapshot, old, experiments = case()
    paths = evaluate_paths(snapshot, old, experiments, {"oct16-veal": dict(enrichment=None, error="Timeout")})["paths"]
    for path in paths.values():
        assert path["unresolved"] == ["oct16-veal"]
        assert path["qualified_metrics"]["false_negatives"] == []
        assert path["qualified_metrics"]["classified_positive_coverage"] == 0
        assert path["final_winner_ids"] == []
        assert path["rows"]["oct16-veal"]["queue_score"] is None


def test_shared_union_excludes_missing_date_diagnostics_from_main_enrichment():
    snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))
    old = baseline(snapshot)
    experiments = {"luna-100": dict(outcomes=[dict(article_id=row["article_id"], classification=None)
                                             for row in snapshot["articles"]])}
    sets = retained_sets(snapshot, old, experiments)
    assert len(sets["luna-100"]) == 25
    assert "saved-sharjah" not in set().union(*sets.values())
