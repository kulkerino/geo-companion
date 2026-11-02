import type { Attribution } from "./api/generated";

// Every shown asset carries its full credit and rights state (data policy).
export function AttributionDetails({ attribution, label }: { attribution: Attribution; label: string }) {
  return (
    <dl className="source" aria-label={label}>
      <dt>Source</dt>
      <dd>
        <a href={attribution.source_url} target="_blank" rel="noreferrer noopener">{attribution.source_title}</a>
      </dd>
      <dt>Attribution</dt>
      <dd>{attribution.attribution_text}</dd>
      <dt>Creator</dt>
      <dd>{attribution.creator}</dd>
      <dt>License</dt>
      <dd>
        <a href={attribution.license_url} target="_blank" rel="noreferrer noopener">{attribution.license_name}</a>
      </dd>
      <dt>Rights status</dt>
      <dd>{attribution.rights_status}</dd>
      <dt>Geographic scope</dt>
      <dd>{attribution.geographic_scope}</dd>
      <dt>Accessed / reviewed</dt>
      <dd>{attribution.accessed_on} / {attribution.reviewed_on}</dd>
    </dl>
  );
}
