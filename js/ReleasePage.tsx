import { Set } from "immutable";

import React, { useState, Fragment } from "react";
import ReactDOM from "react-dom";

import { AverageRating } from "./AverageRating";
import { ReleaseActions } from "./ReleaseActions";
import { RatingWidget } from "./RatingWidget";

import { actOnRelease, rateRelease } from "./api";
import { toggleSet, setOnSuccessEagerly } from "./utils";

interface ReleasePageProps {
  averageRatingContainer: HTMLElement;
  releaseActionsContainer: HTMLElement;
  ratingWidgetContainer: HTMLElement;
  releaseId: string;
  actions: string[];
  userRating: number | null;
  averageRating: number | null;
}

export function ReleasePage(props: ReleasePageProps) {
  const {
    averageRatingContainer,
    releaseActionsContainer,
    ratingWidgetContainer,
    releaseId,
  } = props;

  const [rating, setRating] = useState(props.userRating);
  const [actions, setActions] = useState(Set(props.actions));
  const [averageRating, setAverageRating] = useState(props.averageRating);

  const updateRating = async (newRating: number | null) => {
    const promise = rateRelease(releaseId, newRating);
    setOnSuccessEagerly(promise, rating, setRating, newRating);
    const responseBody = await (await promise).json();

    if ('averageRating' in responseBody) {
      setAverageRating(responseBody.averageRating);
    }
  }

  const toggleAction = async (action: string) => {
    const isUndo = actions.has(action);
    setOnSuccessEagerly(
      actOnRelease(releaseId, action, isUndo),
      actions, setActions, toggleSet(actions, action),
    );
  }

  return (
    <Fragment>
      {
        ReactDOM.createPortal(
          <AverageRating {...{ averageRating }} />,
          averageRatingContainer,
        )
      }
      {
        ReactDOM.createPortal(
          <ReleaseActions {...{ actions, toggleAction }} />,
          releaseActionsContainer,
        )
      }
      {
        ReactDOM.createPortal(
          <RatingWidget {...{ rating, updateRating }} />,
          ratingWidgetContainer,
        )
      }
    </Fragment>
  );
}
