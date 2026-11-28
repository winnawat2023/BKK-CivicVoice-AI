const urgencyLabels = { critical: "CRITICAL", high: "HIGH", normal: "NORMAL", medium: "NORMAL", low: "NORMAL" };

function appendText(parent, tag, value, className = "") {
  const entry = document.createElement(tag);
  if (className) entry.className = className;
  entry.textContent = value;
  parent.append(entry);
}

export function renderSummaryCard({ list, empty, tags, districtCard, districtName }, data, options = {}) {
  const lines = Array.isArray(data?.summary_lines)
    ? data.summary_lines.filter(line => typeof line === "string" && line.trim()).slice(0, 3) : [];
  const fallback = data?.summary_th || data?.summary;
  if (!lines.length && typeof fallback === "string" && fallback.trim()) lines.push(fallback);

  list.replaceChildren();
  for (const line of lines) appendText(list, "li", line);
  list.hidden = !lines.length;
  empty.hidden = !!lines.length;

  const key = String(data?.urgency ?? "").toLowerCase();
  const level = Object.hasOwn(urgencyLabels, key) ? urgencyLabels[key] : null;
  const days = data?.sla_days ?? data?.estimated_sla_days;
  tags.replaceChildren();
  if (level) appendText(tags, "span", level, `tag ${level.toLowerCase()}`);
  for (const label of [data?.sub_category || data?.category, options.showUnit && data?.target_unit,
    Number.isFinite(days) && `SLA คาดการณ์ ${days} วัน`]) {
    if (typeof label === "string" && label.trim()) appendText(tags, "span", label, "tag");
  }
  tags.hidden = !tags.childElementCount;

  const district = options.district || data?.district;
  const name = typeof district === "string" ? district.trim() : "";
  districtCard.hidden = !name;
  districtName.textContent = name ? "สำนักงานเขต" + name.replace(/^(?:สำนักงานเขต|เขต)\s*/u, "") : "";
}
