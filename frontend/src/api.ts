const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ChatResponse = {
  session_id: string;
  action: string;
  reply: string;
  risk_level: string;
  candidates: Array<Record<string, unknown>>;
  comparison?: { products: Array<Record<string, unknown>>; source?: string; source_version?: string; updated_at?: string } | null;
  next_question?: string | null;
  used_tools: string[];
  needs_confirmation: boolean;
  truncated: boolean;
  trace_id: string;
};

export async function sendMessage(sessionId: string, message: string, productSku?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message, channel: "web", ...(productSku ? { product_sku: productSku } : {}) }),
  });
  if (!response.ok) throw new Error(`请求失败（${response.status}）`);
  return response.json() as Promise<ChatResponse>;
}
