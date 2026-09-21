import { DataState } from "@/components/ui";

export default function Loading() {
  return <div className="route-loading" role="status" aria-live="polite"><DataState title="Loading Provena records" message="Reading the selected organization and scope…"/></div>;
}
