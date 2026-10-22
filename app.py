"""Frontend: a Streamlit dashboard for a business owner.

Paste customer reviews (one per line), click Analyze, and see the sentiment,
ratings and most common themes. The dashboard does not call Gemini directly:
it sends each review to the FastAPI backend (api.py), so the AI logic lives in
one service that any other client could also use.

Run it in a second terminal while the backend is running:
    uv run streamlit run app.py
"""

import os
from collections import Counter

import pandas as pd
import requests
import streamlit as st

from database import DB_FILE, init_db, load_history, save_results

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
TIMEOUT_SECONDS = 60
SAMPLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_reviews.txt")


def backend_is_up() -> bool:
    try:
        return requests.get(f"{BACKEND_URL}/health", timeout=5).ok
    except requests.RequestException:
        return False


def analyze_review(review: str) -> dict:
    """Send one review to the backend. Failures are returned as an error row, never raised."""
    try:
        response = requests.post(f"{BACKEND_URL}/analyze", json={"text": review}, timeout=TIMEOUT_SECONDS)
        if not response.ok:
            detail = response.json().get("detail", response.reason) if response.content else response.reason
            raise RuntimeError(f"{response.status_code}: {detail}")
        data = response.json()
        return {"review": review, "label": data["label"], "score": data["score"], "theme": data["theme"], "error": ""}
    except Exception as exc:  # one bad review must not stop the batch
        return {"review": review, "label": "error", "score": None, "theme": "", "error": str(exc)}


def summarize(results: list[dict]) -> dict:
    """Headline numbers for the dashboard, calculated only from successful analyses."""
    ok = [r for r in results if r["label"] != "error"]
    themes = Counter(r["theme"] for r in ok)
    return {
        "total": len(results),
        "analyzed": len(ok),
        "failed": len(results) - len(ok),
        "avg_score": round(sum(r["score"] for r in ok) / len(ok), 1) if ok else None,
        "pct_positive": round(100 * sum(r["label"] == "positive" for r in ok) / len(ok)) if ok else None,
        "labels": Counter(r["label"] for r in ok),
        "themes": themes,
        "top_theme": themes.most_common(1)[0][0] if themes else None,
    }


def main():
    st.set_page_config(page_title="Customer Feedback Analyzer", page_icon="📝", layout="wide")
    init_db()

    st.title("📝 Customer Feedback Analyzer")
    st.write("Paste customer reviews below, one per line, to see how customers feel and what they talk about most.")

    if st.button("Load sample reviews"):
        with open(SAMPLE_FILE, encoding="utf-8") as f:
            st.session_state.reviews_text = f.read()

    reviews_text = st.text_area("Reviews", height=220, key="reviews_text",
                                placeholder="The food was delicious but the delivery took over an hour.")

    if st.button("Analyze", type="primary"):
        reviews = [line.strip() for line in reviews_text.splitlines() if line.strip()]

        if not reviews:
            st.warning("Paste at least one review to analyze.")
        elif not backend_is_up():
            st.error(
                f"Can't reach the backend at {BACKEND_URL}. Start it in another terminal with "
                "`uv run fastapi dev api.py`, then click Analyze again."
            )
        else:
            progress = st.progress(0.0, text="Analyzing reviews...")
            results = []
            for i, review in enumerate(reviews, start=1):
                results.append(analyze_review(review))
                progress.progress(i / len(reviews), text=f"Analyzed {i} of {len(reviews)} reviews")
            progress.empty()
            st.session_state.results = results
            st.session_state.saved = False

    if "results" in st.session_state:
        results = st.session_state.results
        summary = summarize(results)

        st.subheader("Summary")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Reviews analyzed", f"{summary['analyzed']} / {summary['total']}")
        col2.metric("Average score", f"{summary['avg_score']} / 5" if summary["avg_score"] is not None else "–")
        col3.metric("Positive", f"{summary['pct_positive']}%" if summary["pct_positive"] is not None else "–")
        col4.metric("Top theme", summary["top_theme"] or "–")

        if summary["failed"]:
            first_error = next(r["error"] for r in results if r["label"] == "error")
            st.warning(f"{summary['failed']} review(s) could not be analyzed. First error: {first_error}")

        if summary["analyzed"]:
            chart1, chart2 = st.columns(2)
            with chart1:
                st.markdown("**Sentiment**")
                st.bar_chart(pd.Series(summary["labels"], name="reviews"))
            with chart2:
                st.markdown("**Themes**")
                st.bar_chart(pd.Series(summary["themes"], name="reviews").sort_values(ascending=False))

        st.subheader("Results")
        st.dataframe(pd.DataFrame(results).drop(columns=["error"] if not summary["failed"] else []),
                     hide_index=True)

        if st.button("💾 Save to database", disabled=st.session_state.get("saved", False) or not summary["analyzed"]):
            saved = save_results(results)
            st.session_state.saved = True
            st.success(f"Saved {saved} review(s) to {DB_FILE}")

    with st.expander("📚 Saved history"):
        history = load_history()
        if history:
            st.write(f"Total saved so far: {len(history)}")
            st.dataframe(pd.DataFrame(history), hide_index=True)
        else:
            st.write("Nothing saved yet. Analyze some reviews and click Save to database.")


if __name__ == "__main__":
    main()
