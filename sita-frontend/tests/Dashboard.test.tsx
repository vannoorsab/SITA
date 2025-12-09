import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Dashboard from "../src/components/Dashboard";

// Mock socket.io-client so we can emit events manually
jest.mock("socket.io-client", () => {
  const handlers: Record<string, (payload: any) => void> = {};

  return {
    io: jest.fn(() => ({
      on: (event: string, cb: (payload: any) => void) => {
        handlers[event] = cb;
      },
      disconnect: jest.fn(),
    })),
    __handlers: handlers,
  };
});

// Mock API module and capture approveRemediation calls
const approveMock = jest.fn().mockResolvedValue(undefined);

jest.mock("../src/api", () => ({
  BACKEND: "http://localhost:8080",
  approveRemediation: (...args: any[]) => approveMock(...args),
}));

describe("Dashboard agent trace and approval", () => {
  it("calls approveRemediation when Approve button is clicked", async () => {
    const socketModule = require("socket.io-client");

    render(<Dashboard />);

    const fakeAlert = {
      id: "alert-1",
      category: "authentication",
      severity: "HIGH",
      summary: "Multiple failed logins from 10.0.0.1",
      plan_trace: [
        { message: "Analyze alerts", status: "succeeded" },
        { message: "Run remediation playbook", status: "awaiting_approval" },
      ],
      remediation_id: "rem-123",
      agent_confidence: 92,
      agent_rationale: "High confidence based on repeated failures and IP reputation.",
    };

    // Simulate incoming cloud-alert from socket
    const handlers = socketModule.__handlers as Record<string, (payload: any) => void>;
    handlers["cloud-alert"]?.(fakeAlert);

    // Expand trace and click Approve
    const showTraceButton = await screen.findByRole("button", { name: /show trace/i });
    fireEvent.click(showTraceButton);

    const approveButton = await screen.findByRole("button", { name: /approve/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(approveMock).toHaveBeenCalledWith("rem-123");
    });
  });
});
