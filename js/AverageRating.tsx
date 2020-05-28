import React from "react";

export interface AverageRatingProps {
  averageRating: number | null;
}

export function AverageRating({ averageRating }: AverageRatingProps) {
  if (!averageRating) {
    return null;
  }

  return (
    <span className="average-rating unselectable">
      { averageRating.toFixed(1) }
    </span>
  );
}
