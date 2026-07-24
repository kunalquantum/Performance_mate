"""
Recommender/predictor for LinkedIn post performance.

Not a prediction tool. A recommender. It says: given past posts that look like
this draft, here is what the pattern suggests. With 125 posts we cannot
promise more than that.

Three models, one per target:
    - post_score       : the composite (0-100), our internal rank score
    - Impressions      : raw view count
    - engagement_rate  : reactions per view

Each model is a Gradient Boosting Regressor over a common feature set that
combines the text-derived features and the manually-tagged image features.
Categorical features are one-hot encoded via a fitted OneHotEncoder so the
same encoder can transform a draft at predict time.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


CATEGORICAL = ["theme", "cta_type", "length_band", "day_of_week",
               "format_inferred", "has_face_in_image", "text_on_image",
               "image_colour_theme", "target_region", "media_type"]

NUMERIC = ["word_count", "hook_len", "hashtag_count", "emoji_count",
           "line_breaks", "has_link", "has_question"]

TARGETS = ["post_score", "Impressions", "engagement_rate"]


def _feature_frame(df):
    """Pull only the columns we know how to model, cleaned up."""
    cols = CATEGORICAL + NUMERIC
    present = [c for c in cols if c in df.columns]
    X = df[present].copy()
    for c in CATEGORICAL:
        if c in X.columns:
            X[c] = X[c].fillna("unknown").astype(str)
            X.loc[X[c].str.strip() == "", c] = "unknown"
            X.loc[X[c].str.lower() == "nan", c] = "unknown"
    for c in NUMERIC:
        if c in X.columns:
            X[c] = pd.to_numeric(X[c], errors="coerce")
    return X, present


def _build_pipeline(cat_cols, num_cols):
    cat_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    num_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
    ])
    pre = ColumnTransformer([
        ("cat", cat_pipe, cat_cols),
        ("num", num_pipe, num_cols),
    ])
    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.85, min_samples_leaf=2, random_state=0,
    )
    return Pipeline([("pre", pre), ("model", model)])


def train_models(scored):
    """Fit one Gradient Boosting Regressor per target.

    Returns a dict with the fitted pipelines, the feature list used, and the
    training frame X so we can do nearest-neighbour lookups later.
    """
    X, present = _feature_frame(scored)
    cat = [c for c in CATEGORICAL if c in present]
    num = [c for c in NUMERIC if c in present]

    models = {}
    for target in TARGETS:
        if target not in scored.columns:
            continue
        y = pd.to_numeric(scored[target], errors="coerce")
        mask = y.notna() & (~X.isna().all(axis=1))
        if mask.sum() < 15:
            continue
        pipe = _build_pipeline(cat, num)
        pipe.fit(X[mask], y[mask])
        models[target] = pipe

    return {
        "models": models,
        "cat": cat,
        "num": num,
        "X_train": X,
        "scored_train": scored.reset_index(drop=True),
    }


def predict(bundle, draft):
    """Given a draft dict, return {target: predicted_value}."""
    row = {c: draft.get(c, np.nan) for c in bundle["cat"] + bundle["num"]}
    for c in bundle["cat"]:
        v = row.get(c)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            row[c] = "unknown"
        else:
            row[c] = str(v)
    X_draft = pd.DataFrame([row], columns=bundle["cat"] + bundle["num"])
    out = {}
    for tgt, pipe in bundle["models"].items():
        out[tgt] = float(pipe.predict(X_draft)[0])
    return out


def find_similar(bundle, draft, n=3):
    """kNN-style nearest posts to a draft. Similarity = Hamming on categorical
    match count, plus a small number-features distance. Returns the top-N rows
    of scored_train ordered by similarity."""
    X = bundle["X_train"].copy()
    scored = bundle["scored_train"]
    cat = bundle["cat"]
    num = bundle["num"]

    cat_match = np.zeros(len(X))
    for c in cat:
        d = str(draft.get(c, "unknown"))
        cat_match += (X[c].astype(str).fillna("unknown") == d).astype(int)

    if num:
        n_diffs = []
        for c in num:
            v = draft.get(c)
            if v is None or (isinstance(v, float) and np.isnan(v)):
                continue
            col = pd.to_numeric(X[c], errors="coerce")
            span = (col.max() - col.min()) or 1
            n_diffs.append(1 - (abs(col - v) / span).clip(0, 1))
        if n_diffs:
            num_score = pd.concat(n_diffs, axis=1).mean(axis=1)
            score = cat_match + num_score * len(cat)  # weight cats higher
        else:
            score = cat_match
    else:
        score = cat_match

    idx = np.argsort(-score.values)[:n]
    return scored.iloc[idx].assign(_similarity=score.values[idx])


PHOTO_FEATURES = ["has_face_in_image", "text_on_image", "image_colour_theme",
                  "media_type", "format_inferred"]

TEXT_FEATURES = ["theme", "cta_type", "day_of_week", "length_band",
                 "word_count", "hook_len", "hashtag_count", "has_link",
                 "has_question", "target_region", "emoji_count", "line_breaks"]


def _baseline_draft(bundle):
    """A neutral draft where every feature is at the training-set mode
    (categorical) or median (numeric). Predicting on this returns the model's
    baseline expectation."""
    X = bundle["X_train"]
    baseline = {}
    for c in bundle["cat"]:
        m = X[c].mode()
        baseline[c] = m.iloc[0] if not m.empty else "unknown"
    for c in bundle["num"]:
        baseline[c] = float(pd.to_numeric(X[c], errors="coerce").median())
    return baseline


def predict_partial(bundle, draft, keep_features, target="post_score"):
    """Predict a target using only the features in keep_features, with every
    other feature held at the training baseline. Returns a single float."""
    baseline = _baseline_draft(bundle)
    for k in keep_features:
        if k in draft and draft[k] not in (None, ""):
            baseline[k] = draft[k]
    preds = predict(bundle, baseline)
    return preds.get(target)


def contributions(bundle, draft, target="post_score"):
    """Shapley decomposition of the model's prediction into a photo
    contribution and a text contribution.

    For a two-player Shapley split, the identity
        phi_photo + phi_text = v(full) - v(baseline)
    holds EXACTLY for any model (linear or not). That means the scorecards
    displayed to the user can be additive without lying about the model.

    Returns a dict with baseline, photo_contribution, text_contribution and
    the combined prediction. Sum of photo + text + baseline equals combined.
    """
    baseline_draft = _baseline_draft(bundle)

    def with_features(feature_names):
        d = dict(baseline_draft)
        for k in feature_names:
            if k in draft and draft[k] not in (None, ""):
                d[k] = draft[k]
        return d

    photo_only = with_features(PHOTO_FEATURES)
    text_only = with_features(TEXT_FEATURES)
    full = with_features(PHOTO_FEATURES + TEXT_FEATURES)

    B = predict(bundle, baseline_draft).get(target)
    v_photo = predict(bundle, photo_only).get(target)
    v_text = predict(bundle, text_only).get(target)
    v_full = predict(bundle, full).get(target)

    phi_photo = 0.5 * (v_photo - B) + 0.5 * (v_full - v_text)
    phi_text = 0.5 * (v_text - B) + 0.5 * (v_full - v_photo)

    return {
        "baseline": B,
        "photo_contribution": phi_photo,
        "text_contribution": phi_text,
        "combined": v_full,
    }


def what_would_lift(bundle, draft, target="post_score", top_n=5,
                    only_features=None):
    """For each categorical feature, try every value and report the swap that
    changes the predicted target the most. Simple counterfactual analysis, one
    feature at a time."""
    if target not in bundle["models"]:
        return pd.DataFrame()
    base = predict(bundle, draft)[target]
    rows = []
    X = bundle["X_train"]
    feats_to_try = only_features if only_features else bundle["cat"]
    feats_to_try = [f for f in feats_to_try if f in bundle["cat"]]
    for feat in feats_to_try:
        current = str(draft.get(feat, "unknown"))
        options = X[feat].astype(str).fillna("unknown").unique()
        for opt in options:
            if opt == current or opt == "unknown":
                continue
            trial = dict(draft)
            trial[feat] = opt
            new = predict(bundle, trial)[target]
            rows.append({
                "feature": feat, "from": current, "to": opt,
                "delta": new - base, "new_score": new,
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("delta", ascending=False)
    return df.head(top_n).reset_index(drop=True)


def feature_importance(bundle, target="post_score"):
    """Aggregate per-column importance from the tree model. Reads the
    one-hot columns and sums their importance back into the original feature
    name so it's readable."""
    if target not in bundle["models"]:
        return pd.DataFrame()
    pipe = bundle["models"][target]
    model = pipe.named_steps["model"]
    pre = pipe.named_steps["pre"]
    try:
        feat_names = pre.get_feature_names_out()
    except Exception:
        return pd.DataFrame()
    imps = model.feature_importances_
    rows = []
    for name, imp in zip(feat_names, imps):
        # cat__theme_pain_point  or  num__word_count
        parts = name.split("__", 1)
        col_and_val = parts[1] if len(parts) == 2 else name
        # for categorical, keep just the column name so we sum across one-hot
        base_col = col_and_val.split("_")[0] if parts[0] == "num" else \
            (col_and_val.split("_", 1)[0] if "_" in col_and_val else col_and_val)
        # more careful splitting for categorical - the column name is the prefix
        # that matches one of bundle["cat"]
        base = None
        if parts[0] == "num":
            base = col_and_val
        else:
            for c in bundle["cat"]:
                if col_and_val.startswith(c + "_") or col_and_val == c:
                    base = c
                    break
        if base is None:
            base = base_col
        rows.append({"feature": base, "importance": float(imp)})
    df = pd.DataFrame(rows)
    return (df.groupby("feature", as_index=False)["importance"].sum()
              .sort_values("importance", ascending=False)
              .reset_index(drop=True))
