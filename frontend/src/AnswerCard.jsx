const CONTRACTS = {
  full_time: "nhân viên chính thức",
  intern: "thực tập sinh",
  contractor: "cộng tác viên",
}

const OUTCOMES = {
  answered: "Đã chọn quy định",
  conflict: "Xung đột",
  no_policy: "Không đủ căn cứ",
  unknown_topic: "Ngoài chủ đề",
}

function Lines({ title, items, empty }) {
  return (
    <div>
      <p className="kicker">{title}</p>
      {items.length === 0 ? <p className="lede">{empty}</p> : (
        <ul>
          {items.map((item) => (
            <li key={`${item.document_id}-${item.version}-${item.reason}`}>
              <span className="mono">{item.document_id} v{item.version}</span>
              {item.reason ? ` · ${item.reason}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function AnswerCard({ result, onOpen }) {
  if (!result) return null
  const persona = result.persona
  const contract = CONTRACTS[persona.employment_type] || persona.employment_type
  const winner = result.winner
  return (
    <article className={`card ${result.outcome}`}>
      <div className="card-head">
        <div>
          <h2 className="who">{persona.name}</h2>
          <p className="lede">{persona.org_path}</p>
          <p className="lede">{contract} · ngày {result.as_of}</p>
        </div>
        <span className="pill">{OUTCOMES[result.outcome] || result.outcome}</span>
      </div>
      <p className="answer">{result.answer}</p>
      <p className="reason">{result.reason}</p>
      <div className="source">
        <p className="kicker">Tài liệu dùng</p>
        {winner ? (
          <button className="text-link" type="button" onClick={() => onOpen(`${winner.document_id}-v${winner.version}`)}>
            {winner.document_id} v{winner.version}
          </button>
        ) : <strong>Không có</strong>}
        {winner?.title ? <span className="lede">{winner.title}</span> : null}
      </div>
      <Lines
        title="Bổ sung"
        items={result.supplements.map((item) => ({ ...item, reason: "Bổ sung cho mức bắt buộc" }))}
        empty="Không có."
      />
      <Lines title="Bị thay" items={result.overridden} empty="Không có quy định cấp rộng hơn bị thay." />
      <Lines title="Thấy được nhưng không dùng" items={result.visible_rejected} empty="Không có." />
    </article>
  )
}
