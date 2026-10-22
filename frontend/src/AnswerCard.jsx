const CONTRACTS = {
  full_time: "nhân viên chính thức",
  intern: "thực tập sinh",
  contractor: "cộng tác viên",
}

const CLEARANCE = {
  internal: "nội bộ",
  confidential: "mật",
  restricted: "hạn chế",
}

const ROLES = {
  employee: "nhân viên",
  intern: "thực tập",
  manager: "quản lý",
  policy_admin: "quản trị chính sách",
  contractor: "cộng tác viên",
}

const OUTCOMES = {
  answered: "Đã chọn quy định",
  conflict: "Xung đột",
  no_policy: "Không đủ căn cứ",
  unknown_topic: "Ngoài chủ đề",
}

const STATUS_LABELS = {
  published: "Đang ban hành",
  draft: "Dự thảo",
  superseded: "Đã thay thế",
  archived: "Lưu trữ",
}

function formatDay(value) {
  if (!value) return ""
  const [year, month, day] = value.split("-")
  return `${day}/${month}/${year}`
}

function formatWindow(from, to) {
  if (!from) return ""
  if (!to) return `từ ${formatDay(from)}`
  return `${formatDay(from)} – ${formatDay(to)}`
}

function versionIdOf(item) {
  return `${item.document_id}-v${item.version}`
}

function DecisionStack({ items, onOpen }) {
  return (
    <div className="card-section">
      <p className="kicker">Chồng quyết định</p>
      {items?.length ? <ol className="stack">
        {items.map((item) => (
          <li className={item.place} key={`${item.document_id}-${item.version}-${item.place}`}>
            <span className="lede">{item.level_label} · {item.audience_name} · {item.label}</span>
            <button
              className="text-link"
              type="button"
              onClick={() => onOpen(versionIdOf(item), {
                text: item.statement,
                used: item.place !== "replaced",
                versionId: versionIdOf(item),
              })}
            >
              {item.document_id} v{item.version}
            </button>
            {item.place === "replaced" ? <span className="lede">Không được dùng cho câu trả lời này.</span> : null}
            {item.statement ? <p className="statement">{item.statement}</p> : null}
          </li>
        ))}
      </ol> : <p className="lede">Không có.</p>}
    </div>
  )
}

function Lines({ title, items, empty }) {
  return (
    <div className="card-section">
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
  const clearance = CLEARANCE[persona.clearance] || persona.clearance
  const roles = (persona.roles || []).map((role) => ROLES[role] || role).join(", ")
  const winner = result.winner
  return (
    <article className={`card ${result.outcome}`}>
      <div className="card-lead">
      <div className="card-head">
        <h2 className="who">{persona.name}</h2>
        <span className="pill">{OUTCOMES[result.outcome] || result.outcome}</span>
      </div>
      <div className="identity">
        <p>{persona.org_path}</p>
        <p>{roles} · {contract} · mức {clearance}</p>
        <p>Ngày hỏi {formatDay(result.as_of)}</p>
      </div>
      <p className="answer">{result.answer}</p>
      {result.reason && result.reason !== result.answer ? <p className="reason">{result.reason}</p> : null}
      <div className="source">
        <p className="kicker">Tài liệu dùng</p>
        {winner ? (
          <button
            className="text-link"
            type="button"
            onClick={() => onOpen(`${winner.document_id}-v${winner.version}`, {
              text: winner.statement,
              used: true,
              versionId: `${winner.document_id}-v${winner.version}`,
            })}
          >
            {winner.document_id} v{winner.version}
          </button>
        ) : <strong>Không có</strong>}
        {winner?.title ? <span className="lede">{winner.title}</span> : null}
        {winner ? (
          <span className="lede">
            Hiệu lực {formatWindow(winner.effective_from, winner.effective_to)}
            {winner.owner ? ` · ${winner.owner}` : ""}
          </span>
        ) : null}
      </div>
      </div>
      <div className="card-section">
        <p className="kicker">
          Các phiên bản{result.versions?.[0] ? ` của ${result.versions[0].document_id}` : ""}
        </p>
        {(result.versions || []).length > 0 ? (
          <ol className="timeline">
            {result.versions.map((item) => (
              <li className={item.mark === "current" ? "current" : ""} key={item.version_id}>
                {item.readable ? (
                  <button
                    className="text-link"
                    type="button"
                    onClick={() => onOpen(item.version_id, {
                      text: item.mark === "current" ? winner?.statement : "",
                      used: item.mark === "current",
                      versionId: item.version_id,
                    })}
                  >
                    {item.document_id} v{item.version}
                  </button>
                ) : <span className="mono">{item.document_id} v{item.version}</span>}
                <span className="lede">
                  {item.status === "draft" || item.status === "archived"
                    ? `${STATUS_LABELS[item.status] || item.status} · `
                    : ""}
                  {formatWindow(item.effective_from, item.effective_to)}
                  {" · "}
                  {item.reason}
                </span>
              </li>
            ))}
          </ol>
        ) : <p className="lede">Không có.</p>}
      </div>
      <DecisionStack items={result.stack} onOpen={onOpen} />
      <Lines title="Thấy được nhưng không dùng" items={result.visible_rejected} empty="Không có." />
    </article>
  )
}
