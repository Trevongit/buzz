import { getFeature } from "./manifest";
import { resolveEnabled } from "./resolveEnabled";
import { getOverrides } from "./store";

/**
 * Preview-feature resolution for non-React callers (git, etc.).
 *
 * Matches `useFeatureEnabled`: unknown / graduated ids fail-open (stable),
 * manifest rows use the user override then `defaultEnabled` (off if omitted).
 */
export function previewFeatureEnabled(featureId: string): boolean {
  const feature = getFeature(featureId);
  if (!feature) return true;
  return resolveEnabled(featureId, getOverrides(), feature.defaultEnabled);
}
