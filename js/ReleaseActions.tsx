import React from "react";
import { Set } from "immutable";

interface ActionButtonProps {
  active: boolean;
  icon: string;
  descs: string[];
  toggle: () => void;
}

export function ActionButton({
  active, icon, descs, toggle,
}: ActionButtonProps) {
  const onClick = (event: React.SyntheticEvent) => {
    event.preventDefault();
    toggle();
  }
  return (
    <a
      className={active ? "selected" : ""}
      href="#"
      onClick={onClick}
    >
      <i className="material-icons">{ icon }</i>
      { descs[active ? 1 : 0] }
    </a>
  );
}

//

interface ReleaseActionsProps {
  actions: Set<string>;
  toggleAction: (action: string) => void;
}

export function ReleaseActions({
  actions,
  toggleAction,
}: ReleaseActionsProps) {
  const [save, listen] = [
    <ActionButton
      icon="playlist_add"
      descs={["Save", "Saved"]}
      active={actions.has("save")}
      toggle={() => toggleAction("save")}
    />,
    <ActionButton
      icon="headset"
      descs={["Listened to", "Listened to"]}
      active={actions.has("listen")}
      toggle={() => toggleAction("listen")}
    />
  ];

  const buttons = actions.has("rate") ? [save] : [save, listen];

  return (
    <ol className="action-list inline unselectable">
      { buttons.map(button => <li>{ button }</li>) }
    </ol>
  );
}
