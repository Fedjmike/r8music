import { pick } from "lodash";

import React from "react";
import { render } from "react-dom";

import { Tracklist } from "./Tracklist";
import { ReleaseActions } from "./ReleaseActions";

for (const container of document.getElementsByClassName("track-list")) {
  const tracklistProps = pick(window, [
    "trackInfo", "picks", "comparisonPicks", "comparisonUser"
  ]);
  const element = <Tracklist {...tracklistProps} />;
  render(element, container);
}

for (const container of document.getElementsByClassName("release-actions")) {
  const { releaseId, releaseActions } = window as any;
  const element = <ReleaseActions {...{ releaseId, actions: releaseActions }} />;
  render(element, container);
}
