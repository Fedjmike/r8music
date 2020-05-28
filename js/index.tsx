import { pick } from "lodash";

import React from "react";
import { render } from "react-dom";

import { Tracklist } from "./Tracklist";
import { ReleasePage } from "./ReleasePage";

const [
  tracklistContainer,
  releaseContainer,
  averageRatingContainer,
  releaseActionsContainer,
  ratingWidgetContainer
] = [
  "track-list",
  "release-container",
  "average-rating",
  "release-actions",
  "rating-widget"
].map(document.getElementById.bind(document))

if (tracklistContainer) {
  const tracklistProps = pick(window as any, [
    "trackInfo", "picks", "comparisonPicks", "comparisonUser"
  ]);
  render(<Tracklist {...tracklistProps} />, tracklistContainer);
}

if (
  releaseContainer && averageRatingContainer &&
  releaseActionsContainer && ratingWidgetContainer
) {
  const {
    releaseId, releaseActions, userRating, averageRating,
  } = window as any;
  render(
    <ReleasePage
      {...{
        averageRatingContainer,
        releaseActionsContainer,
        ratingWidgetContainer,
        releaseId,
        userRating, 
        averageRating,
        actions: releaseActions,
      }}
    />,
    releaseContainer
  );
}
