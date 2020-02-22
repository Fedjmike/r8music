import { pick } from "lodash";

import React from "react";
import { render } from "react-dom";

import { Tracklist } from "./Tracklist";

for (const container of document.getElementsByClassName("track-list")) {
  const tracklistProps = pick(window, [
    "trackInfo", "picks", "comparisonPicks", "comparisonUser"
  ]);
  const element = <Tracklist {...tracklistProps} />;
  render(element, container);
}
