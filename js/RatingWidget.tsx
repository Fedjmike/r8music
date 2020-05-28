import React from "react";

export function RatingWidget({ rating, updateRating }: any) {
  const renderButton = (n: number) => {
    const selected = n == rating;
    return (
      <li
        key={n}
        className={selected ? "selected" : ""}
        onClick={() => { updateRating(selected ? null : n) }}
      >
        { n }
      </li>
    );
  }

  // In reverse for styling reasons
  const ratings = [1, 2, 3, 4, 5, 6, 7, 8].reverse();

  return (
    <ol className="rating unselectable">
      { ratings.map(renderButton) }
    </ol>
  );
}
