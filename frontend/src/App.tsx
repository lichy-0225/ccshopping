import { useMemo, useState } from "react";
import { sendMessage } from "./api";

type Candidate = { sku_id?: string; name?: string; spec?: string; price?: number; match_reasons?: string[]; 注意事项?: string };
type Message = { role: "user" | "assistant"; content: string; candidates?: Candidate[]; usedTools?: string[] };

function RichText({ content }: { content: string }) {
  return <>{content.split("\n").map((line, index) => <span key={`${index}-${line}`}>{line.split(/(\*\*.*?\*\*)/g).map((part, partIndex) => part.startsWith("**") && part.endsWith("**") ? <strong key={partIndex}>{part.slice(2, -2)}</strong> : <span key={partIndex}>{part}</span>)}{index < content.split("\n").length - 1 && <br />}</span>)}</>;
}

const examples = ["我预算 200 元，想买无香洁面", "最近皮肤有点干，怎么选？", "这两个商品有什么区别？"];

const products = [
  { sku: "P101", name: "云感氨基酸舒润洁面乳", price: 169, image: "/products/P101.jpeg" },
  { sku: "P102", name: "净澈控油洁面啫喱", price: 149, image: "/products/P102.jpeg" },
  { sku: "P201", name: "焕亮果酸细致精华液", price: 229, image: "/products/P201.jpeg" },
  { sku: "P202", name: "屏护神经酰胺保湿乳", price: 259, image: "/products/P202.jpeg" },
  { sku: "P203", name: "水漾轻盈保湿凝露", price: 219, image: "/products/P203.jpeg" },
  { sku: "P301", name: "随行旅行分装瓶礼盒", price: 49, image: "/products/P301.jpeg" },
];

export default function App() {
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "你好，我是澄初个人护理导购。你可以告诉我想解决的问题、预算或偏好。" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canSend = useMemo(() => input.trim().length > 0 && !loading, [input, loading]);

  async function submit(message = input) {
    const text = message.trim();
    if (!text || loading) return;
    setInput(""); setError(null); setMessages((current) => [...current, { role: "user", content: text }]); setLoading(true);
    try {
      const data = await sendMessage(sessionId, text);
      setMessages((current) => [...current, { role: "assistant", content: data.reply, candidates: data.candidates as Candidate[], usedTools: data.used_tools }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally { setLoading(false); }
  }

  function reset() { setSessionId(crypto.randomUUID()); setMessages([{ role: "assistant", content: "已开启新会话。你想了解哪类个人护理产品？" }]); setError(null); }

  return <main className="page"><section className="shell">
    <header className="header"><div><p className="eyebrow">澄初个人护理</p><h1>AI 商品导购</h1><p className="subtitle">先了解需求，再给你合适的选择</p></div><button className="ghost" onClick={reset}>重新开始</button></header>
    <section className="product-rail" aria-label="商品宣传图"><div className="product-rail-header"><div><span className="eyebrow">PRODUCTS</span><h2>澄初商品</h2></div><span className="rail-hint">左右滑动浏览</span></div><div className="product-track">{products.map((product) => <article className="promo-card" key={product.sku}><img src={product.image} alt={`${product.sku} ${product.name}`} /><div className="promo-info"><span>{product.sku}</span><strong>{product.name}</strong><b>¥{product.price}</b></div></article>)}</div></section>
    <div className="examples">{examples.map((example) => <button key={example} onClick={() => submit(example)}>{example}</button>)}</div>
    <section className="chat" aria-live="polite">{messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span>{message.role === "assistant" ? "导购" : "我"}</span><p><RichText content={message.content} /></p>{message.candidates?.map((candidate) => <div className="product-card" key={candidate.sku_id}><strong>{candidate.name}</strong><small>{candidate.spec} · ¥{candidate.price}</small>{candidate.match_reasons?.map((reason) => <small key={reason}>{reason}</small>)}{candidate["注意事项"] && <small>注意：{candidate["注意事项"]}</small>}</div>)}{message.usedTools?.length ? <small className="trace">工具：{message.usedTools.join("、")}</small> : null}</div>)}{loading && <div className="message assistant"><span>导购</span><p className="typing">正在整理建议…</p></div>}</section>
    {error && <div className="error"><span>{error}</span><button onClick={() => submit(messages[messages.length - 1]?.content ?? "")}>重试</button></div>}
    <form className="composer" onSubmit={(event) => { event.preventDefault(); void submit(); }}><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="例如：我预算 200 元，想买无香洁面" disabled={loading} /><button type="submit" disabled={!canSend}>发送</button></form>
    <p className="status">Agent V2：工具调用与商品事实由后端控制。</p>
  </section></main>;
}
