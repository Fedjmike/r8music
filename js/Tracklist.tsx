import React, { useState } from "react";

function PickIcon(props) {
  const Element = "href" in props ? "a" : "span";
  return (
    <Element {...props} className={"track-pick " + props.className} >
      <i className="material-icons">stars</i>
    </Element>
  )
}

function Track({
  track,
  isPicked,
  alsoPickedBy,
}) {
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
          className={"action clickable " + (isPicked ? "selected" : "")}
          name="pick" href="#" data-track-id={track.id}
          title="Select as a pick"
        />
      </span>
      { track.runtime_str && <time>{ track.runtime_str }</time> }
    </li>
  );
}

export function Tracklist({
  trackInfo,
  picks,
  comparisonUser,
  comparisonPicks,
}) {
  const [isExpanded, setExpanded] = useState(false);
  const toggleExpanded = () => setExpanded(!isExpanded);
  
  const renderTrack = (track) =>
    <Track track={track} key={track.id}
      isPicked={picks.includes(track.id)}
      alsoPickedBy={comparisonPicks.includes(track.id) && comparisonUser}
    />

  const expandOrContractButton =
    <i
      className="expand-button material-icons tiny"
      title={isExpanded ? "Contract the tracklist": "Show the full tracklist"}
      onClick={toggleExpanded}
    >{ isExpanded ? "expand_less" : "expand_more" }</i>;

  const { tracks, runtime } = trackInfo;
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
