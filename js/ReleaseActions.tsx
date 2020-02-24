import React, { useState } from "react";
import { Set } from "immutable";
import { actOnRelease } from "./api";
import { toggleSet, setOnSuccessEagerly } from "./utils";

export function ActionButton({
  active, icon, descs, toggleAction
}) {
  const onClick = (event: React.SyntheticEvent) => {
    event.preventDefault();
    toggleAction();
  }
  return (
    <a className={active ? "selected" : ""} href="#" onClick={onClick}>
      <i className="material-icons">{ icon }</i>
      { descs[active ? 1 : 0] }
    </a>
  );
}

export function ReleaseActions({ releaseId, actions: actionsInput }: {
  releaseId: string;
  actions: string[];
}) {
  const [actions, setActions] = useState(Set(actionsInput));

  const toggleAction = async (action: string) => {
    const isUndo = actions.has(action);
    setOnSuccessEagerly(
      actOnRelease(releaseId, action, isUndo),
      actions, setActions, toggleSet(actions, action),
    );
  }

  const [save, listen] = [
    <ActionButton icon="playlist_add" descs={["Save", "Saved"]}
      active={actions.has("save")}
      toggleAction={() => toggleAction("save")}
    />,
    <ActionButton icon="headset" descs={["Listened to", "Listened to"]}
      active={actions.has("listen")}
      toggleAction={() => toggleAction("listen")}
    />
  ];

  const buttons = actions.has("rate") ? [save] : [save, listen];

  return (
    <ol className="action-list inline unselectable">
      { buttons.map(button => <li>{ button }</li>) }
    </ol>
  );
}
