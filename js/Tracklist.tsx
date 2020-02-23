import React, { useState } from "react";
import { Set } from "immutable";
import * as API from "./api";
import { toggleSet } from "./utils";

function PickIcon(props: any) {
  const Element = "href" in props ? "a" : "span";
  return (
    <Element {...props} className={"track-pick " + props.className} >
      <i className="material-icons">stars</i>
    </Element>
  )
}

//

interface TrackProps {
  track: API.Track;
  isPicked: boolean;
  togglePicked: () => void;
  alsoPickedBy?: API.Username;
}

function Track({
  track,
  isPicked,
  togglePicked,
  alsoPickedBy,
}: TrackProps) {
  const onClick = (event: React.SyntheticEvent) => {
    event.preventDefault();
    togglePicked();
  }
  return (
    <li>
      <span className="track-title">
        { track.title }
        { alsoPickedBy &&
          <PickIcon
            className="comparison-selected"
            title={alsoPickedBy + "'s pick"}
          /> }
        <PickIcon
          className={"action " + (isPicked ? "selected" : "")}
          title="Select as a pick"
          href="#" onClick={onClick}
        />
      </span>
      { track.runtime_str && <time>{ track.runtime_str }</time> }
    </li>
  );
}

//

interface TracklistProps {
  trackInfo: {
    tracks: API.Track[];
    runtime?: string;
  };
  picks: string[];
  comparisonUser?: API.Username;
  comparisonPicks: string[];
}

export function Tracklist({
  trackInfo: { tracks, runtime },
  picks, comparisonUser, comparisonPicks,
}: TracklistProps) {
  const [isExpanded, setExpanded] = useState(false);
  const [pickState, setPicks] = useState(Set(picks));

  const toggleExpanded = () => setExpanded(!isExpanded);
  
  const togglePick = async (trackId: string) => {
    const isUnpick = pickState.has(trackId);
    await API.pickTrack(trackId, isUnpick);
    setPicks(toggleSet(pickState, trackId));
  }
  
  const renderTrack = (track: API.Track) =>
    <Track track={track} key={track.id}
      isPicked={pickState.has(track.id)}
      togglePicked={() => togglePick(track.id)}
      alsoPickedBy={comparisonPicks.includes(track.id) ? comparisonUser : undefined}
    />

  const expandOrContractButton =
    <i
      className="expand-button material-icons tiny"
      title={isExpanded ? "Contract the tracklist" : "Show the full tracklist"}
      onClick={toggleExpanded}
    >{ isExpanded ? "expand_less" : "expand_more" }</i>;

  const showRuntime = runtime && tracks.length > 1;
  const isLargeTracklist = tracks.length > 17;
  const visibleTracks = isLargeTracklist && !isExpanded
    ? tracks.slice(0, 13) : tracks;
  
  return (
    <ol className="tracks">
      { visibleTracks.map(renderTrack) }
      { isLargeTracklist && expandOrContractButton }
      { showRuntime && <li className="total clearfix"><time>{ runtime }</time></li> }
    </ol>
  );
}
