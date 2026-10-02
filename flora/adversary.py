"""adversary.py - classifier of the passive adversary (experiments 04, 04b, 04c).

v1.1 used HistGradientBoostingClassifier with default settings (200 iterations, unlimited
leaf size). With a few hundred positive frames it over-fitted the frame-length feature, so that
adding length to time of day *lowered* the out-of-fold AUC (a negative "gain from length"),
which a competent adversary cannot suffer. v1.2 regularises the model (small trees, large
leaves, L2 penalty, early stopping on an inner validation split)."""
from sklearn.ensemble import HistGradientBoostingClassifier


def make_adversary(seed: int):
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=8,
                                          min_samples_leaf=100, l2_regularization=1.0,
                                          early_stopping=True, validation_fraction=0.2,
                                          n_iter_no_change=20, random_state=seed)
