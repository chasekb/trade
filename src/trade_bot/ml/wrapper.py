"""Wrapper class for trading models to support both regression and classification."""

from typing import Any, Optional
import numpy as np


class TradingModelWrapper:
    """Wrapper for both regressor (return) and classifier (win prob) models."""
    
    def __init__(self, regressor: Any, classifier: Any = None):
        self.regressor = regressor
        self.classifier = classifier
        
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict expected return using regressor."""
        return self.regressor.predict(X)
        
    def predict_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        """Predict win probability using classifier."""
        if self.classifier is None:
            return None
        return self.classifier.predict_proba(X)
