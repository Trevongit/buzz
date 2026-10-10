import { createFileRoute } from "@tanstack/react-router";

import { PulseScreen } from "@/features/pulse/ui/PulseScreen";
import {
  parseProfilePanelTab,
  parseProfilePanelView,
  type ProfilePanelTab,
  type ProfilePanelView,
} from "@/features/profile/ui/UserProfilePanelUtils";
import { usePreviewFeatureWarning } from "@/shared/features";

type PulseRouteSearch = {
  profile?: string;
  profileTab?: ProfilePanelTab;
  profileView?: ProfilePanelView;
};

function validatePulseSearch(
  search: Record<string, unknown>,
): PulseRouteSearch {
  return {
    profile:
      typeof search.profile === "string" && search.profile.length > 0
        ? search.profile
        : undefined,
    profileTab: parseProfilePanelTab(search.profileTab) ?? undefined,
    profileView: parseProfilePanelView(search.profileView) ?? undefined,
  };
}

export const Route = createFileRoute("/pulse")({
  validateSearch: validatePulseSearch,
  component: PulseRouteComponent,
});

function PulseRouteComponent() {
  usePreviewFeatureWarning("pulse");
  return <PulseScreen />;
}
