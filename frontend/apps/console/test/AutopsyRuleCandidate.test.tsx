import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

const proposeRuleCandidate = vi.fn(async () => ({
  change_id: "CHG-42",
  state: "draft",
  cluster_id: "cluster-1",
  note: "draft only",
}));
const autopsyClusters = vi.fn(async () => ({
  complaint_count: 2,
  clustering_method: "test clustering",
  clustering_disclosure: "Synthetic complaints",
  hypothesis: false,
  synthetic: true,
  note: "",
  languages: { en: 2 },
  clusters: [
    {
      cluster_id: "cluster-1",
      label: "Unknown recurring charge",
      size: 2,
      status: "confirmed",
      status_label: "Confirmed by CX",
      mapping_label: "No existing rule mapping",
      hypothesis: false,
      suggested_rule_id: null,
      languages: { en: 2 },
      representative_masked_complaints: ["A masked complaint"],
      synthetic_demo_trend: { current: 2 },
      reviews: [],
    },
  ],
}));
const client = {
  autopsyClusters,
  proposeRuleCandidate,
  reviewCluster: vi.fn(),
  supersedeClusterReview: vi.fn(),
};

vi.mock("@/components/StaffSessionProvider", () => ({
  useStaffSession: () => ({
    client,
    session: { subject: "cx:roshan", roles: ["cx_engineer"] },
    generation: 0,
    hasPermission: (permission: string) =>
      ["desk:queue:read", "autopsy:review", "rule:draft"].includes(permission),
  }),
}));

const { default: AutopsyPage } = await import("@/app/autopsy/page");

describe("Complaint Autopsy rule candidate", () => {
  test("sends a confirmed cluster to Policy Studio as a draft", async () => {
    render(<AutopsyPage />);

    await screen.findByText("Unknown recurring charge");
    fireEvent.change(screen.getByLabelText("Policy key"), {
      target: { value: "refund.auto_cap_lkr" },
    });
    fireEvent.change(screen.getByLabelText("Candidate value"), {
      target: { value: "1500" },
    });
    fireEvent.change(screen.getByLabelText("Rationale"), {
      target: { value: "confirmed complaint pattern" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send draft to Policy Studio" }));

    await waitFor(() =>
      expect(proposeRuleCandidate).toHaveBeenCalledWith("cluster-1", {
        key: "refund.auto_cap_lkr",
        value: "1500",
        rationale: "confirmed complaint pattern",
      }),
    );
    expect(await screen.findByText(/Draft CHG-42 created/)).toBeInTheDocument();
  });
});
