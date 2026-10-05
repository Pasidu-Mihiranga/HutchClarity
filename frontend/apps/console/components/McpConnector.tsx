"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  Field,
  Input,
  Select,
  Spinner,
  Tab,
  TabList,
  TabPanel,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Tabs,
} from "@clarity/ui";
import type { McpConnectorView, McpHealthView, McpProfileView } from "@clarity/sdk";
import { useStaffSession } from "@/components/StaffSessionProvider";

/**
 * The MCP connector panel (OPS01).
 *
 * The admin page carried a hard-coded list of three names under the line
 * "Placeholder inventory - not connected to live MCP clients". The server it
 * was describing was real the whole time: `clarity-mcp` is its own deployable
 * serving MCP over Streamable HTTP, verifying OAuth 2.1 bearer tokens as a
 * resource server, and choosing a tool profile from the token's scope.
 *
 * So this panel reports that server as configured, and the tool list comes
 * from the registry rather than being restated: a tool added to
 * `ClarityMCPServer` appears here without anyone remembering to update a page.
 *
 * **Connecting is the point of it.** An operator does not want to read a tool
 * list, they want another system talking to this one. "Connect a system"
 * produces the configuration that system needs, for its chosen profile, ready
 * to paste.
 *
 * **It never shows a secret.** The client id, the issuer and the endpoints are
 * public; the client secret lives in the operator's identity provider and the
 * generated snippets reference it as an environment variable (I14).
 */

/** How alarming each safety level is. Nothing here executes; L3 proposes. */
const LEVEL_TONE: Record<string, "neutral" | "warning" | "danger"> = {
  L1: "neutral",
  L2: "warning",
  L3: "danger",
};

/** What each level means, since the wire value is a bare code. */
const LEVEL_MEANING: Record<string, string> = {
  L1: "read",
  L2: "low risk",
  L3: "proposes money",
};

function useCopy(): [string | null, (key: string, text: string) => void] {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = useCallback((key: string, text: string) => {
    void (async () => {
      try {
        await navigator.clipboard.writeText(text);
        setCopied(key);
        window.setTimeout(() => setCopied((current) => (current === key ? null : current)), 2000);
      } catch {
        // Clipboard access can be refused (no permission, insecure origin).
        // The text is on screen and selectable either way, so this is not
        // worth an error banner.
      }
    })();
  }, []);
  return [copied, copy];
}

/** A copyable block. The text stays selectable when the clipboard is refused. */
function Snippet({
  id,
  label,
  text,
  copied,
  onCopy,
}: {
  id: string;
  label: string;
  text: string;
  copied: string | null;
  onCopy: (key: string, text: string) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.1em] text-fg-muted">
          {label}
        </span>
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Copy ${label}`}
          onClick={() => onCopy(id, text)}
        >
          {copied === id ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="overflow-x-auto rounded-md border border-border bg-surface-2 p-3 font-mono text-xs leading-5 text-fg">
        {text}
      </pre>
    </div>
  );
}

export function McpConnector() {
  const { client, generation, hasPermission } = useStaffSession();
  const canManage = hasPermission("admin:manage");

  const [connector, setConnector] = useState<McpConnectorView | null>(null);
  const [health, setHealth] = useState<McpHealthView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [probing, setProbing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [profileName, setProfileName] = useState("");
  const [clientName, setClientName] = useState("hutch-clarity");
  const [copied, copy] = useCopy();

  const load = useCallback(() => {
    if (!canManage) return;
    void client
      .mcpConnector()
      .then((found) => {
        setConnector(found);
        setProfileName((current) => current || found.profiles[0]?.profile || "");
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not read the MCP connector"),
      );
  }, [canManage, client]);

  useEffect(load, [load, generation]);

  async function probe() {
    setProbing(true);
    setError(null);
    try {
      setHealth(await client.mcpHealth());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The health check failed");
    } finally {
      setProbing(false);
    }
  }

  if (!canManage) return null;

  if (connector === null) {
    return (
      <Card className="space-y-3">
        <h2 className="font-medium">MCP connector</h2>
        {error ? (
          <Alert tone="danger">{error}</Alert>
        ) : (
          <p className="flex items-center gap-2 text-sm text-fg-muted">
            <Spinner size="sm" label="Loading the MCP connector" />
            Loading…
          </p>
        )}
      </Card>
    );
  }

  const { server, authorization, profiles, guarantees } = connector;
  const selected: McpProfileView | undefined =
    profiles.find((p) => p.profile === profileName) ?? profiles[0];

  const key = clientName.trim() || "hutch-clarity";
  const discoveryConfig = JSON.stringify(
    { mcpServers: { [key]: { type: "http", url: server.resource_url } } },
    null,
    2,
  );
  const bearerConfig = JSON.stringify(
    {
      mcpServers: {
        [key]: {
          type: "http",
          url: server.resource_url,
          headers: { Authorization: "Bearer ${CLARITY_MCP_TOKEN}" },
        },
      },
    },
    null,
    2,
  );
  const tokenCommand = [
    `curl -s -X POST "${authorization.token_endpoint ?? "<token endpoint>"}" \\`,
    `  -d grant_type=client_credentials \\`,
    `  -d client_id=${authorization.client_id} \\`,
    `  -d "client_secret=$CLARITY_MCP_SECRET" \\`,
    `  -d "scope=${selected?.scope ?? ""}" \\`,
    `  -d "resource=${authorization.resource_indicator}"`,
  ].join("\n");

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="admin-mcp" className="font-medium">
          MCP connector
        </h2>
        <div className="flex items-center gap-2">
          {health ? (
            <Badge tone={health.reachable ? "success" : "danger"}>{health.status}</Badge>
          ) : (
            <Badge>not checked</Badge>
          )}
          <Button variant="secondary" size="sm" loading={probing} onClick={() => void probe()}>
            Check
          </Button>
          <Button size="sm" onClick={() => setConnecting(true)}>
            Connect a system
          </Button>
        </div>
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}

      <p className="text-sm text-fg-muted">
        {server.title} serves MCP over {server.transport}. It is a separate
        process from this console, so a green console says nothing about it
        until you check.
      </p>

      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase text-fg-muted">Endpoint</dt>
          <dd className="break-all font-mono text-xs">{server.resource_url}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-fg-muted">Discovery</dt>
          <dd className="break-all font-mono text-xs">{authorization.discovery_url}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-fg-muted">Authorization</dt>
          <dd className="text-xs">{authorization.flow}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-fg-muted">Last check</dt>
          <dd className="text-xs">
            {health
              ? `${new Date(health.checked_at).toLocaleString()}${health.detail ? ` · ${health.detail}` : ""}`
              : "not checked in this session"}
          </dd>
        </div>
      </dl>

      {!authorization.configured ? (
        <Alert tone="warning" title="No identity provider is configured">
          The server still refuses every unauthenticated call, so nothing can
          connect until <code>CLARITY_KEYCLOAK_ISSUER</code> points at a real
          issuer. The configuration below is complete apart from the token
          endpoint, which comes from that issuer.
        </Alert>
      ) : null}

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.1em] text-fg-muted">
          Tools, by profile
        </h3>
        <Tabs defaultValue={profiles[0]?.profile ?? ""} value={profileName} onValueChange={setProfileName}>
          <TabList label="MCP tool profiles">
            {profiles.map((profile) => (
              <Tab key={profile.profile} value={profile.profile}>
                {profile.profile}
              </Tab>
            ))}
          </TabList>
          {profiles.map((profile) => (
            <TabPanel key={profile.profile} value={profile.profile}>
              <p className="mb-2 text-xs text-fg-muted">
                A token needs the scope <code>{profile.scope}</code> to get this
                set.{" "}
                {profile.case_bound
                  ? "It is bound to one case, so one subscriber's agent cannot reach another's."
                  : "It is not bound to a case."}
              </p>
              <Table
                caption={`Tools available to the ${profile.profile} profile`}
                scrollLabel={`${profile.profile} tools`}
                className="text-xs"
              >
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Tool</TableHeaderCell>
                    <TableHeaderCell>Level</TableHeaderCell>
                    <TableHeaderCell>What it does</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {profile.tools.map((tool) => (
                    <TableRow key={tool.name}>
                      <TableCell className="font-mono">{tool.name}</TableCell>
                      <TableCell>
                        <Badge tone={LEVEL_TONE[tool.level] ?? "neutral"}>
                          {tool.level}
                          {LEVEL_MEANING[tool.level] ? ` · ${LEVEL_MEANING[tool.level]}` : ""}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-fg-muted">{tool.description}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TabPanel>
          ))}
        </Tabs>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-[0.1em] text-fg-muted">
          What a connected model cannot do
        </h3>
        <ul className="list-disc space-y-1 pl-5 text-xs text-fg-muted">
          {guarantees.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </div>

      <Dialog
        open={connecting}
        onClose={() => setConnecting(false)}
        title="Connect a system to Clarity"
        description="Give the system below the configuration for the profile you want it to have. The profile comes from the token's scope, so this is what decides which tools it sees."
        size="lg"
        footer={
          <Button onClick={() => setConnecting(false)}>Done</Button>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field
              label="Profile"
              hint="The tool set the connecting system gets. It cannot widen this by asking."
            >
              {(control) => (
                <Select
                  {...control}
                  value={selected?.profile ?? ""}
                  onChange={(event) => setProfileName(event.target.value)}
                >
                  {profiles.map((profile) => (
                    <option key={profile.profile} value={profile.profile}>
                      {profile.profile} — {profile.tools.length} tools
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Server name" hint="How the connecting system will list it.">
              {(control) => (
                <Input
                  {...control}
                  value={clientName}
                  onChange={(event) => setClientName(event.target.value)}
                />
              )}
            </Field>
          </div>

          <Alert tone="info" title="Which of the two below you need">
            If the connecting system supports OAuth discovery, give it the first
            one and it will find the authorization server itself. If it only
            takes a bearer header, use the second and fetch a token with the
            command underneath.
          </Alert>

          <Snippet
            id="discovery"
            label="Client config, OAuth discovery"
            text={discoveryConfig}
            copied={copied}
            onCopy={copy}
          />
          <Snippet
            id="bearer"
            label="Client config, bearer header"
            text={bearerConfig}
            copied={copied}
            onCopy={copy}
          />
          <Snippet
            id="token"
            label={`Get a token for ${selected?.profile ?? "this profile"}`}
            text={tokenCommand}
            copied={copied}
            onCopy={copy}
          />

          <Alert tone="warning" title="The secret is not here, on purpose">
            {authorization.secret_hint}
          </Alert>

          <dl className="grid gap-2 text-xs sm:grid-cols-2">
            <div>
              <dt className="uppercase text-fg-muted">Client id</dt>
              <dd className="font-mono">{authorization.client_id}</dd>
            </div>
            <div>
              <dt className="uppercase text-fg-muted">Scope</dt>
              <dd className="font-mono">{selected?.scope}</dd>
            </div>
            <div>
              <dt className="uppercase text-fg-muted">Audience</dt>
              <dd className="font-mono">{authorization.audience}</dd>
            </div>
            <div>
              <dt className="uppercase text-fg-muted">Resource indicator</dt>
              <dd className="break-all font-mono">{authorization.resource_indicator}</dd>
            </div>
          </dl>

          <p className="text-xs text-fg-muted">
            The resource indicator is checked on every call (RFC 8707): a token
            your client obtained for some other service will not work here just
            because the same realm signed it.
          </p>
        </div>
      </Dialog>
    </Card>
  );
}
