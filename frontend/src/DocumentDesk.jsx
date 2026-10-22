import { useEffect, useMemo, useRef, useState } from "react"
import { post, remove, request } from "./api"

const EMPTY = {
  document_id: "",
  version: 1,
  title: "",
  topic: "leave.annual",
  customTopic: "",
  phrases: "",
  owner_org: "apx/apt/hr",
  audience_orgs: ["apx/apt"],
  audience_type: "subtree",
  classification: "internal",
  contracts: ["full_time"],
  status: "published",
  required_role: "",
  effective_from: "2026-01-01",
  effective_to: "",
  override_mode: "default",
  supplementTarget: "",
  supersedes: "",
  content: "",
}

const STATUS_LABELS = {
  published: "Đang ban hành",
  draft: "Dự thảo",
  superseded: "Đã thay thế",
  archived: "Lưu trữ",
}

const CLASSIFICATION_LABELS = {
  internal: "Nội bộ",
  confidential: "Mật",
  restricted: "Hạn chế",
}

const AUDIENCE_LABELS = {
  subtree: "Gồm cả cấp dưới",
  exact: "Đúng đơn vị",
  explicit: "Danh sách chỉ định",
}

const ROLE_LABELS = {
  employee: "Nhân viên",
  intern: "Thực tập sinh",
  manager: "Quản lý",
  policy_admin: "Quản trị chính sách",
  contractor: "Cộng tác viên",
}

const OVERRIDE_LABELS = {
  default: "Mặc định",
  mandatory: "Bắt buộc",
  supplement: "Bổ sung",
}

function formFromDocument(document, topics) {
  const knownTopic = topics.some((topic) => topic.id === document.topic)
  return {
    document_id: document.document_id,
    version: document.version,
    title: document.title,
    topic: knownTopic ? document.topic : (topics[0]?.id || ""),
    customTopic: knownTopic ? "" : document.topic,
    phrases: (document.match_phrases || []).join(", "),
    owner_org: document.owner_org,
    audience_orgs: document.audience_orgs || [],
    audience_type: document.audience_type,
    classification: document.classification,
    contracts: document.allowed_contract_types || [],
    status: document.status,
    required_role: document.required_role || "",
    effective_from: document.effective_from || "",
    effective_to: document.effective_to || "",
    override_mode: document.override_mode,
    supplementTarget: document.supplement_target || "",
    supersedes: document.supersedes || "",
    content: document.content,
  }
}

function CitedContent({ content, text }) {
  const index = text ? content.indexOf(text) : -1
  if (index < 0) return <pre className="doc-read">{content}</pre>
  return (
    <pre className="doc-read">
      {content.slice(0, index)}
      <mark>{content.slice(index, index + text.length)}</mark>
      {content.slice(index + text.length)}
    </pre>
  )
}

export default function DocumentDesk({ catalog, documents, onSaved, focusId, citation, personaId, asOf, canManage, personas, onPersonaChange }) {
  const formCard = useRef(null)
  const [form, setForm] = useState(EMPTY)
  const [query, setQuery] = useState("")
  const [message, setMessage] = useState("")
  const [tone, setTone] = useState("")
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [opened, setOpened] = useState(null)
  const [openError, setOpenError] = useState("")
  const requestId = useRef(0)
  const personaKey = useRef(personaId)

  if (personaKey.current !== personaId) {
    personaKey.current = personaId
    requestId.current += 1
    setOpened(null)
    setForm(EMPTY)
    setOpenError("")
  }

  useEffect(() => {
    if (focusId) openVersion(focusId)
  }, [focusId, personaId])

  useEffect(() => {
    if (!opened || citation?.versionId !== opened.version_id) return
    document.querySelector(".doc-read mark")?.scrollIntoView({ block: "center" })
  }, [opened, citation])

  async function openVersion(versionId) {
    const current = ++requestId.current
    setOpenError("")
    setConfirming(false)
    setOpened(null)
    setForm(EMPTY)
    try {
      const params = new URLSearchParams({ persona_id: personaId, as_of: asOf })
      const detail = await request(`/api/documents/${encodeURIComponent(versionId)}?${params}`)
      if (current !== requestId.current) return
      setOpened(detail)
      setForm(formFromDocument(detail, catalog.topics))
      formCard.current?.scrollIntoView({ block: "start" })
    } catch (error) {
      if (current !== requestId.current) return
      setOpened(null)
      setForm(EMPTY)
      setOpenError(error.message)
    }
  }

  async function removeOpened() {
    if (!opened) return
    const label = `${opened.document_id} phiên bản ${opened.version}`
    setRemoving(true)
    setTone("")
    setMessage("Đang xóa...")
    try {
      const params = new URLSearchParams({ persona_id: personaId })
      await remove(`/api/documents/${encodeURIComponent(opened.version_id)}?${params}`)
      setOpened(null)
      setConfirming(false)
      setForm(EMPTY)
      setTone("ok")
      setMessage(`Đã xóa ${label}.`)
      await onSaved()
    } catch (error) {
      setTone("error")
      setMessage(error.message)
    } finally {
      setRemoving(false)
    }
  }

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return documents
    return documents.filter((item) =>
      `${item.document_id} ${item.title} ${item.topic} ${item.status}`.toLowerCase().includes(needle)
    )
  }, [documents, query])

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
  }

  function toggleContract(value) {
    setForm((current) => {
      const has = current.contracts.includes(value)
      const contracts = has
        ? current.contracts.filter((item) => item !== value)
        : [...current.contracts, value]
      return { ...current, contracts }
    })
  }

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setTone("")
    setMessage("Đang lưu...")
    try {
      const saved = await post("/api/documents", {
        persona_id: personaId,
        document_id: form.document_id,
        version: Number(form.version),
        title: form.title,
        topic: form.customTopic.trim() || form.topic,
        match_phrases: form.phrases.split(",").map((item) => item.trim()).filter(Boolean),
        owner_org: form.owner_org,
        audience_orgs: form.audience_orgs,
        audience_type: form.audience_type,
        classification: form.classification,
        allowed_contract_types: form.contracts,
        status: form.status,
        required_role: form.required_role || null,
        effective_from: form.effective_from,
        effective_to: form.effective_to || null,
        override_mode: form.override_mode,
        supplement_target: form.supplementTarget || null,
        supersedes: form.supersedes ? Number(form.supersedes) : null,
        content: form.content,
      })
      setTone("ok")
      setMessage(`Đã lưu ${saved.version_id}. Hỏi lại để thấy tài liệu nếu người được chọn nằm trong phạm vi.`)
      setForm((current) => ({ ...current, document_id: "", content: "" }))
      await onSaved()
    } catch (error) {
      setTone("error")
      setMessage(error.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="desk">
      <form className="form-card" ref={formCard} onSubmit={save}>
        <div className="library-head">
          <h2>{opened ? opened.title : "Thêm tài liệu"}</h2>
          <label>Người đang xem
            <select value={personaId} onChange={(event) => onPersonaChange(event.target.value)}>
              {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name} · {persona.org} · {persona.clearance === "restricted" ? "hạn chế" : persona.clearance === "confidential" ? "mật" : "nội bộ"}</option>)}
            </select>
          </label>
        </div>
        {opened && citation?.versionId === opened.version_id ? (
          <div className="cited-doc">
            {citation.used === false ? (
              <p className="banner">Không được dùng cho câu trả lời này.</p>
            ) : <p className="kicker">Đoạn đã trích</p>}
            <CitedContent content={opened.content} text={citation.text} />
          </div>
        ) : null}
        <div className="actions">
          {opened ? null : <p className="lede">Thư viện chỉ hiện tài liệu người này được đọc.</p>}
          {opened ? (
            <button className="ghost" type="button" onClick={() => { setOpened(null); setConfirming(false); setForm(EMPTY) }}>Tạo mới</button>
          ) : null}
        </div>
        <div className="grid">
          <label>Mã tài liệu
            <input value={form.document_id} placeholder="APT-ENG-015" onChange={(event) => update("document_id", event.target.value)} required />
          </label>
          <label>Phiên bản
            <input type="number" min="1" value={form.version} onChange={(event) => update("version", event.target.value)} required />
          </label>
          <label className="wide">Tên tài liệu
            <input value={form.title} onChange={(event) => update("title", event.target.value)} required />
          </label>
          <label>Chủ đề
            <select value={form.topic} onChange={(event) => update("topic", event.target.value)}>
              {catalog.topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.label}</option>)}
            </select>
          </label>
          <label>Chủ đề mới
            <input value={form.customTopic} placeholder="travel.allowance" onChange={(event) => update("customTopic", event.target.value)} />
          </label>
          <label className="wide">Cụm từ nhận diện, cách nhau bởi dấu phẩy
            <input value={form.phrases} placeholder="công tác" onChange={(event) => update("phrases", event.target.value)} />
          </label>
          <label>Đơn vị ban hành
            <select value={form.owner_org} onChange={(event) => update("owner_org", event.target.value)}>
              {catalog.orgs.map((org) => <option key={org.id} value={org.id}>{org.label}</option>)}
            </select>
          </label>
          <label>Kiểu phạm vi
            <select value={form.audience_type} onChange={(event) => update("audience_type", event.target.value)}>
              {catalog.audience_types.map((item) => (
                <option key={item} value={item}>{AUDIENCE_LABELS[item] || item}</option>
              ))}
            </select>
          </label>
          <label className="wide">Phạm vi áp dụng
            <select
              multiple
              value={form.audience_orgs}
              onChange={(event) => update("audience_orgs", [...event.target.selectedOptions].map((option) => option.value))}
              required
            >
              {catalog.orgs.map((org) => <option key={org.id} value={org.id}>{org.label}</option>)}
            </select>
          </label>
          <label>Mức bảo mật
            <select value={form.classification} onChange={(event) => update("classification", event.target.value)}>
              {catalog.classifications.map((item) => (
                <option key={item} value={item}>{CLASSIFICATION_LABELS[item] || item}</option>
              ))}
            </select>
          </label>
          <label>Trạng thái
            <select value={form.status} onChange={(event) => update("status", event.target.value)}>
              {catalog.statuses.map((item) => <option key={item} value={item}>{STATUS_LABELS[item] || item}</option>)}
            </select>
          </label>
          <label>Loại hợp đồng được áp dụng
            <span className="checks">
              {[
                ["full_time", "Chính thức"],
                ["intern", "Thực tập"],
                ["contractor", "Cộng tác"],
              ].map(([value, label]) => (
                <label key={value}>
                  <input type="checkbox" checked={form.contracts.includes(value)} onChange={() => toggleContract(value)} />
                  {label}
                </label>
              ))}
            </span>
          </label>
          <label>Vai trò được đọc
            <select value={form.required_role} onChange={(event) => update("required_role", event.target.value)}>
              <option value="">Mọi vai trò được đọc</option>
              {catalog.roles.map((role) => (
                <option key={role} value={role}>{ROLE_LABELS[role] || role}</option>
              ))}
            </select>
          </label>
          <label>Hiệu lực từ
            <input type="date" value={form.effective_from} onChange={(event) => update("effective_from", event.target.value)} required />
          </label>
          <label>Hiệu lực đến
            <input type="date" value={form.effective_to} onChange={(event) => update("effective_to", event.target.value)} />
          </label>
          <label>Quy tắc ghi đè
            <select value={form.override_mode} onChange={(event) => update("override_mode", event.target.value)}>
              {catalog.override_modes.map((item) => (
                <option key={item} value={item}>{OVERRIDE_LABELS[item] || item}</option>
              ))}
            </select>
          </label>
          <label>Bổ sung cho mã tài liệu
            <input value={form.supplementTarget} placeholder="APX-RW-001" onChange={(event) => update("supplementTarget", event.target.value)} />
          </label>
          <label>Thay phiên bản số
            <input type="number" min="1" value={form.supersedes} onChange={(event) => update("supersedes", event.target.value)} />
          </label>
          <label className="wide">Nội dung
            <textarea value={form.content} onChange={(event) => update("content", event.target.value)} required />
          </label>
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={saving || !canManage}>{canManage ? "Lưu tài liệu" : "Chỉ Admin được lưu"}</button>
        </div>
        {message ? <p className={`banner ${tone}`}>{message}</p> : null}
      </form>
      <aside className="library">
        <div>
          <h2>Thư viện</h2>
          <p className="lede">{documents.length} phiên bản</p>
        </div>
        <label>Lọc
          <input value={query} placeholder="Mã, tên hoặc chủ đề" onChange={(event) => setQuery(event.target.value)} />
        </label>
        {opened ? (
          <div className="actions">
            {confirming ? (
              <>
                <button className="danger" type="button" disabled={removing} onClick={removeOpened}>
                  {removing ? "Đang xóa..." : "Xóa hẳn"}
                </button>
                <button className="ghost" type="button" disabled={removing} onClick={() => setConfirming(false)}>Giữ lại</button>
              </>
            ) : canManage ? (
              <button className="danger" type="button" onClick={() => setConfirming(true)}>Xóa phiên bản này</button>
            ) : null}
          </div>
        ) : null}
        {openError ? <p className="banner error">{openError}</p> : null}
        <div>
          {visible.map((item) => (
            <button
              className={opened?.version_id === item.version_id ? "doc-row active" : "doc-row"}
              type="button"
              key={item.version_id}
              onClick={() => openVersion(item.version_id)}
            >
              <strong className="mono">{item.document_id} v{item.version}</strong>
              <span>{item.title}</span>
              <span className={`status ${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
            </button>
          ))}
        </div>
      </aside>
    </div>
  )
}
