import { useEffect, useMemo, useState } from "react"
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

export default function DocumentDesk({ catalog, documents, onSaved, focusId }) {
  const [form, setForm] = useState(EMPTY)
  const [query, setQuery] = useState("")
  const [message, setMessage] = useState("")
  const [tone, setTone] = useState("")
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [opened, setOpened] = useState(null)
  const [openError, setOpenError] = useState("")

  useEffect(() => {
    if (focusId) openVersion(focusId)
  }, [focusId])

  async function openVersion(versionId) {
    setOpenError("")
    setConfirming(false)
    try {
      setOpened(await request(`/api/documents/${encodeURIComponent(versionId)}`))
    } catch (error) {
      setOpened(null)
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
      await remove(`/api/documents/${encodeURIComponent(opened.version_id)}`)
      setOpened(null)
      setConfirming(false)
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
      <form className="form-card" onSubmit={save}>
        <div>
          <h2>Thêm tài liệu</h2>
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
          <label>Thay phiên bản số
            <input type="number" min="1" value={form.supersedes} onChange={(event) => update("supersedes", event.target.value)} />
          </label>
          <label className="wide">Nội dung
            <textarea value={form.content} onChange={(event) => update("content", event.target.value)} required />
          </label>
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={saving}>Lưu tài liệu</button>
        </div>
        {message ? <p className={`banner ${tone}`}>{message}</p> : null}
      </form>
      <aside className="library">
        <div>
          <h2>Thư viện</h2>
          <p className="lede">{documents.length} phiên bản</p>
        </div>
        {opened ? (
          <article className="reader">
            <div className="actions">
              <button className="ghost" type="button" onClick={() => { setOpened(null); setConfirming(false) }}>Quay lại danh sách</button>
              {confirming ? (
                <>
                  <button className="danger" type="button" disabled={removing} onClick={removeOpened}>
                    {removing ? "Đang xóa..." : "Xóa hẳn"}
                  </button>
                  <button className="ghost" type="button" disabled={removing} onClick={() => setConfirming(false)}>Giữ lại</button>
                </>
              ) : (
                <button className="danger" type="button" onClick={() => setConfirming(true)}>Xóa phiên bản này</button>
              )}
            </div>
            <h2>{opened.title}</h2>
            <p className="mono">{opened.document_id} v{opened.version}</p>
            <p className="lede">
              {STATUS_LABELS[opened.status] || opened.status}
              {" · "}{opened.owner_name}
              {" · "}từ {opened.effective_from}
              {opened.effective_to ? ` đến ${opened.effective_to}` : ""}
            </p>
            <p className="reading">{opened.content}</p>
          </article>
        ) : (
          <>
            <label>Lọc
              <input value={query} placeholder="Mã, tên hoặc chủ đề" onChange={(event) => setQuery(event.target.value)} />
            </label>
            {openError ? <p className="banner error">{openError}</p> : null}
            <div>
              {visible.map((item) => (
                <button className="doc-row" type="button" key={item.version_id} onClick={() => openVersion(item.version_id)}>
                  <strong className="mono">{item.document_id} v{item.version}</strong>
                  <span>{item.title}</span>
                  <span className={`status ${item.status}`}>{STATUS_LABELS[item.status] || item.status}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </aside>
    </div>
  )
}
