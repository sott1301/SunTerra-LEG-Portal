import { type FormEvent, useEffect, useState } from "react";

import "./styles.css";

type HealthStatus = {
  status: string;
  service: string;
  version: string;
};

type Role = "participant" | "leg_admin" | "partner_admin" | "platform_admin";

type PreferredContactChannel = "email" | "phone";

type CurrentUser = {
  id: string;
  email: string;
  display_name: string;
  role: Role;
};

type ParticipantInvitation = {
  token: string;
  email: string;
  display_name: string;
  leg_id: "basadingen";
  status: "pending_email_verification";
};

type InvitationAcceptResponse = {
  access_token: string;
  token_type: "bearer";
  participant_id: string;
  email_verification_required: boolean;
};

type EmailVerificationResponse = {
  participant_id: string;
  email_verified: boolean;
};

type ParticipantMembership = {
  participant_id: string;
  display_name: string;
  email: string;
  leg_id: "basadingen";
  leg_name: string;
  membership_status: "active";
  billing_notice: string;
};

type DocumentVersion = {
  id: string;
  document_key: "portal_terms";
  title: string;
  version: string;
  document_hash: string;
  context: "participant_onboarding";
  published_at: string;
};

type CurrentDocument = DocumentVersion & {
  content: string;
};

type ConsentEvidence = {
  participant_id: string;
  document_version_id: string;
  document_key: "portal_terms";
  version: string;
  document_hash: string;
  context: "participant_onboarding";
  accepted_at: string;
};

type AuditEvent = {
  id: string;
  action: string;
  actor_role: Role;
  created_at: string;
  from_status: string | null;
  to_status: string | null;
  reason: string | null;
};

type ParticipantContactChannels = {
  participant_id: string;
  email: string;
  phone_number: string | null;
  preferred_contact_channel: PreferredContactChannel;
  audit_events: AuditEvent[];
};

type MutationRequest = {
  id: string;
  participant_id: string;
  leg_id: "basadingen";
  mutation_type: "address";
  mode: "regular";
  status: "submitted" | "approved" | "rejected";
  quarter: string;
  quarter_end: string;
  participant_deadline: string;
  effective_date: string;
  submitted_at: string;
  reviewed_at: string | null;
  review_reason: string | null;
  new_address: {
    street: string;
    postal_code: string;
    city: string;
    country: string;
  };
  audit_events: AuditEvent[];
};

type AdminMutationRequest = MutationRequest & {
  participant: {
    participant_id: string;
    display_name: string;
    email: string;
  };
};

type MutationPackage = {
  schema_version: "mutation-package.v1";
  package_id: string;
  leg_id: "basadingen";
  quarter: string;
  effective_date: string;
  records: Array<{
    mutation_request_id: string;
    participant_id: string;
    mutation_type: "address";
    mode: "regular";
    effective_date: string;
    new_address: {
      street: string;
      postal_code: string;
      city: string;
      country: string;
    };
  }>;
  hash: string;
  generated_at: string;
  status_history: Array<{
    status: "created";
    actor_id: string;
    actor_role: Role;
    created_at: string;
  }>;
};

type BackendState =
  | { kind: "checking" }
  | { kind: "connected"; health: HealthStatus }
  | { kind: "offline" };

type SessionState =
  | { kind: "anonymous" }
  | { kind: "authenticated"; token: string; user: CurrentUser };

const demoRoles: Array<{ role: Role; label: string; workspaceTitle: string }> = [
  {
    role: "participant",
    label: "Teilnehmer",
    workspaceTitle: "Mein Mitgliederbereich",
  },
  {
    role: "leg_admin",
    label: "LEG Admin",
    workspaceTitle: "LEG Verwaltung",
  },
  {
    role: "partner_admin",
    label: "Gemeinde/EW",
    workspaceTitle: "Gemeinde/EW Arbeitsplatz",
  },
  {
    role: "platform_admin",
    label: "Plattform",
    workspaceTitle: "Plattform Administration",
  },
];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
const devTokenStorageKey = "sunterra.devToken";

export function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });
  const [session, setSession] = useState<SessionState>({ kind: "anonymous" });
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [participantInvitation, setParticipantInvitation] =
    useState<ParticipantInvitation | null>(null);
  const [onboardingToken, setOnboardingToken] = useState("");
  const [emailVerification, setEmailVerification] =
    useState<EmailVerificationResponse | null>(null);
  const [participantMembership, setParticipantMembership] =
    useState<ParticipantMembership | null>(null);
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentVersion, setDocumentVersion] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [publishedDocumentVersion, setPublishedDocumentVersion] =
    useState<DocumentVersion | null>(null);
  const [currentDocument, setCurrentDocument] =
    useState<CurrentDocument | null>(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [consentSaved, setConsentSaved] = useState(false);
  const [consentHistory, setConsentHistory] = useState<ConsentEvidence[]>([]);
  const [contactChannels, setContactChannels] =
    useState<ParticipantContactChannels | null>(null);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [preferredContactChannel, setPreferredContactChannel] =
    useState<PreferredContactChannel>("email");
  const [contactChannelSaved, setContactChannelSaved] = useState(false);
  const [contactChannelError, setContactChannelError] = useState("");
  const [mutationQuarter, setMutationQuarter] = useState("2026-Q3");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressPostalCode, setAddressPostalCode] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressCountry, setAddressCountry] = useState("CH");
  const [mutationRequests, setMutationRequests] = useState<MutationRequest[]>(
    [],
  );
  const [mutationError, setMutationError] = useState("");
  const [adminMutationRequests, setAdminMutationRequests] = useState<
    AdminMutationRequest[]
  >([]);
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>(
    {},
  );
  const [adminMutationError, setAdminMutationError] = useState("");
  const [packageQuarter, setPackageQuarter] = useState("2026-Q3");
  const [mutationPackage, setMutationPackage] =
    useState<MutationPackage | null>(null);
  const [mutationPackageError, setMutationPackageError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/health`);
        const health = (await response.json()) as HealthStatus;

        if (isMounted) {
          setBackend({ kind: "connected", health });
        }
      } catch {
        if (isMounted) {
          setBackend({ kind: "offline" });
        }
      }
    }

    void loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  async function loadCurrentUser(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      window.localStorage.removeItem(devTokenStorageKey);
      setSession({ kind: "anonymous" });
      return;
    }

    const user = (await response.json()) as CurrentUser;
    setSession({ kind: "authenticated", token, user });
    if (user.role === "participant") {
      void loadCurrentDocument(token);
      void loadContactChannels(token);
    }
    if (user.role === "leg_admin") {
      void loadAdminMutationRequests(token);
    } else {
      setAdminMutationRequests([]);
    }
  }

  function loginAs(role: Role) {
    const token = `dev:${role}`;
    window.localStorage.setItem(devTokenStorageKey, token);
    void loadCurrentUser(token);
  }

  async function createParticipantInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const response = await fetch(
      `${apiBaseUrl}/api/admin/participant-invitations`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: inviteEmail,
          display_name: inviteDisplayName,
        }),
      },
    );

    if (response.ok) {
      const invitation = (await response.json()) as ParticipantInvitation;
      setParticipantInvitation(invitation);
    }
  }

  async function publishDocumentVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const response = await fetch(`${apiBaseUrl}/api/admin/document-versions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        document_key: "portal_terms",
        title: documentTitle,
        version: documentVersion,
        content: documentContent,
        context: "participant_onboarding",
      }),
    });

    if (response.ok) {
      const published = (await response.json()) as DocumentVersion;
      setPublishedDocumentVersion(published);
    }
  }

  async function loadCurrentDocument(token: string) {
    const response = await fetch(
      `${apiBaseUrl}/api/documents/current?document_key=portal_terms`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (response.ok) {
      const document = (await response.json()) as CurrentDocument;
      setCurrentDocument(document);
    }
  }

  async function loadConsentHistory(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/participants/me/consent-evidence`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const history = (await response.json()) as ConsentEvidence[];
      setConsentHistory(history);
    }
  }

  async function loadContactChannels(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/participants/me/contact-channels`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const channels = (await response.json()) as ParticipantContactChannels;
      setContactChannels(channels);
      setPhoneNumber(channels.phone_number ?? "");
      setPreferredContactChannel(channels.preferred_contact_channel);
    }
  }

  async function loadAdminMutationRequests(token: string) {
    const response = await fetch(
      `${apiBaseUrl}/api/admin/mutation-requests?status=submitted`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (response.ok) {
      const records = (await response.json()) as AdminMutationRequest[];
      setAdminMutationRequests(records);
    }
  }

  function contactChannelLabel(channel: PreferredContactChannel) {
    return channel === "phone" ? "Telefon" : "E-Mail";
  }

  async function saveContactChannels(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setContactChannelSaved(false);
    setContactChannelError("");
    const response = await fetch(`${apiBaseUrl}/api/participants/me/contact-channels`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        phone_number: phoneNumber.trim() || null,
        preferred_contact_channel: preferredContactChannel,
      }),
    });

    if (response.ok) {
      const channels = (await response.json()) as ParticipantContactChannels;
      setContactChannels(channels);
      setPhoneNumber(channels.phone_number ?? "");
      setPreferredContactChannel(channels.preferred_contact_channel);
      setContactChannelSaved(true);
      return;
    }

    const error = (await response.json()) as { detail?: unknown };
    setContactChannelError(
      typeof error.detail === "string"
        ? error.detail
        : "Kontaktkanäle konnten nicht gespeichert werden",
    );
  }

  async function reviewAdminMutationRequest(
    mutationRequestId: string,
    decision: "approved" | "rejected",
  ) {
    if (session.kind !== "authenticated") {
      return;
    }

    setAdminMutationError("");
    const response = await fetch(
      `${apiBaseUrl}/api/admin/mutation-requests/${mutationRequestId}/review-decision`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(
          decision === "rejected"
            ? {
                decision,
                reason: reviewReasons[mutationRequestId] ?? "",
              }
            : { decision },
        ),
      },
    );

    if (response.ok) {
      const updated = (await response.json()) as AdminMutationRequest;
      setAdminMutationRequests((current) =>
        current.map((mutationRequest) =>
          mutationRequest.id === updated.id ? updated : mutationRequest,
        ),
      );
      return;
    }

    const error = (await response.json()) as { detail?: string };
    setAdminMutationError(
      error.detail ?? "Mutation konnte nicht entschieden werden",
    );
  }

  async function createMutationPackage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setMutationPackageError("");
    const response = await fetch(`${apiBaseUrl}/api/admin/mutation-packages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        quarter: packageQuarter,
      }),
    });

    if (response.ok) {
      const created = (await response.json()) as MutationPackage;
      setMutationPackage(created);
      return;
    }

    const error = (await response.json()) as { detail?: string };
    setMutationPackageError(
      error.detail ?? "Mutationspaket konnte nicht erstellt werden",
    );
  }

  async function downloadMutationPackageArtifact(
    packageId: string,
    artifact: "json" | "csv" | "pdf",
  ) {
    if (session.kind !== "authenticated") {
      return;
    }

    const response = await fetch(
      `${apiBaseUrl}/api/admin/mutation-packages/${packageId}/${artifact}`,
      {
        headers: {
          Authorization: `Bearer ${session.token}`,
        },
      },
    );

    if (!response.ok) {
      setMutationPackageError("Export konnte nicht geladen werden");
      return;
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `mutation-package-${packageId}.${artifact}`;
    link.click();
    URL.revokeObjectURL(objectUrl);
  }

  async function submitConsentEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (
      session.kind !== "authenticated" ||
      currentDocument === null ||
      !consentChecked
    ) {
      return;
    }

    const response = await fetch(`${apiBaseUrl}/api/participants/me/consent-evidence`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        document_version_id: currentDocument.id,
        context: "participant_onboarding",
        accepted: true,
      }),
    });

    if (response.ok) {
      setConsentSaved(true);
      await loadConsentHistory(session.token);
    }
  }

  async function submitAddressMutation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setMutationError("");
    const response = await fetch(`${apiBaseUrl}/api/participants/me/mutation-requests`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        mutation_type: "address",
        mode: "regular",
        requested_quarter: mutationQuarter,
        new_address: {
          street: addressStreet,
          postal_code: addressPostalCode,
          city: addressCity,
          country: addressCountry,
        },
      }),
    });

    if (response.ok) {
      const mutationRequest = (await response.json()) as MutationRequest;
      setMutationRequests((current) => [...current, mutationRequest]);
      return;
    }

    const error = (await response.json()) as { detail?: string };
    setMutationError(error.detail ?? "Mutation konnte nicht eingereicht werden");
  }

  async function acceptParticipantInvitation(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const acceptResponse = await fetch(
      `${apiBaseUrl}/api/auth/invitations/${onboardingToken}/accept`,
      {
        method: "POST",
      },
    );
    const acceptance =
      (await acceptResponse.json()) as InvitationAcceptResponse;

    if (!acceptance.email_verification_required) {
      return;
    }

    const verifyResponse = await fetch(
      `${apiBaseUrl}/api/auth/email-verifications/${onboardingToken}/verify`,
      {
        method: "POST",
      },
    );
    const verification =
      (await verifyResponse.json()) as EmailVerificationResponse;
    setEmailVerification(verification);

    if (!verification.email_verified) {
      return;
    }

    const membershipResponse = await fetch(
      `${apiBaseUrl}/api/participants/me/membership`,
      {
        headers: {
          Authorization: `Bearer ${acceptance.access_token}`,
        },
      },
    );
    const membership =
      (await membershipResponse.json()) as Partial<ParticipantMembership>;

    if (membership.membership_status) {
      const participantMembership = membership as ParticipantMembership;
      setParticipantMembership(participantMembership);
      setSession({
        kind: "authenticated",
        token: acceptance.access_token,
        user: {
          id: participantMembership.participant_id,
          email: participantMembership.email,
          display_name: participantMembership.display_name,
          role: "participant",
        },
      });
      void loadCurrentDocument(acceptance.access_token);
      void loadContactChannels(acceptance.access_token);
    }
  }

  const activeWorkspace =
    session.kind === "authenticated"
      ? demoRoles.find((demoRole) => demoRole.role === session.user.role)
      : undefined;

  const documentConsentForm = currentDocument ? (
    <form className="document-consent" onSubmit={submitConsentEvidence}>
      <h3>{currentDocument.title}</h3>
      <p>Version {currentDocument.version}</p>
      <p>{currentDocument.content}</p>
      <p>{currentDocument.document_hash}</p>
      <label>
        <input
          type="checkbox"
          checked={consentChecked}
          onChange={(event) => setConsentChecked(event.target.checked)}
        />
        Ich stimme dieser Dokumentversion zu
      </label>
      <button type="submit" disabled={!consentChecked}>
        Zustimmen
      </button>
      {consentSaved ? (
        <div className="invitation-result" role="status">
          <p>Einwilligung gespeichert</p>
        </div>
      ) : null}
      {consentHistory.length > 0 ? (
        <section className="consent-history" aria-label="Einwilligungshistorie">
          <h3>Einwilligungshistorie</h3>
          {consentHistory.map((evidence) => (
            <div key={`${evidence.document_version_id}-${evidence.accepted_at}`}>
              <p>Version {evidence.version}</p>
              <p>{evidence.document_hash}</p>
            </div>
          ))}
        </section>
      ) : null}
    </form>
  ) : null;

  const contactChannelEmail =
    contactChannels?.email ??
    (session.kind === "authenticated" ? session.user.email : "");
  const currentPhoneNumber =
    contactChannels?.phone_number ?? "Keine Telefonnummer hinterlegt";
  const currentContactChannel = contactChannels
    ? contactChannelLabel(contactChannels.preferred_contact_channel)
    : contactChannelLabel(preferredContactChannel);

  const contactChannelForm = (
    <section className="contact-channels" aria-label="Kontaktkanäle">
      <form className="invitation-form contact-channel-form" onSubmit={saveContactChannels}>
        <h3>Kontaktkanäle</h3>
        <div className="contact-channel-current">
          <p>E-Mail: {contactChannelEmail}</p>
          <p>Aktuelle Telefonnummer: {currentPhoneNumber}</p>
          <p>Aktueller Kanal: {currentContactChannel}</p>
        </div>
        <label>
          Telefonnummer
          <input
            type="tel"
            value={phoneNumber}
            onChange={(event) => setPhoneNumber(event.target.value)}
          />
        </label>
        <label>
          Bevorzugter Kanal
          <select
            value={preferredContactChannel}
            onChange={(event) =>
              setPreferredContactChannel(
                event.target.value as PreferredContactChannel,
              )
            }
          >
            <option value="email">E-Mail</option>
            <option value="phone">Telefon</option>
          </select>
        </label>
        <button type="submit">Kontaktkanäle speichern</button>
        {contactChannelSaved ? (
          <div className="invitation-result" role="status">
            <p>Kontaktkanäle gespeichert</p>
          </div>
        ) : null}
        {contactChannelError ? (
          <div className="mutation-error" role="alert">
            <p>{contactChannelError}</p>
          </div>
        ) : null}
      </form>
    </section>
  );

  const addressMutationForm = (
    <section className="address-mutations" aria-label="Adressmutation">
      <form className="invitation-form address-mutation-form" onSubmit={submitAddressMutation}>
        <h3>Adressmutation</h3>
        <label>
          Quartal
          <select
            value={mutationQuarter}
            onChange={(event) => setMutationQuarter(event.target.value)}
          >
            <option value="2026-Q1">2026-Q1</option>
            <option value="2026-Q2">2026-Q2</option>
            <option value="2026-Q3">2026-Q3</option>
            <option value="2026-Q4">2026-Q4</option>
          </select>
        </label>
        <label>
          Strasse
          <input
            type="text"
            value={addressStreet}
            onChange={(event) => setAddressStreet(event.target.value)}
            required
          />
        </label>
        <label>
          PLZ
          <input
            type="text"
            value={addressPostalCode}
            onChange={(event) => setAddressPostalCode(event.target.value)}
            required
          />
        </label>
        <label>
          Ort
          <input
            type="text"
            value={addressCity}
            onChange={(event) => setAddressCity(event.target.value)}
            required
          />
        </label>
        <label>
          Land
          <input
            type="text"
            value={addressCountry}
            onChange={(event) => setAddressCountry(event.target.value)}
            required
          />
        </label>
        <button type="submit">Adressmutation einreichen</button>
        {mutationError ? (
          <div className="mutation-error" role="alert">
            <p>{mutationError}</p>
          </div>
        ) : null}
      </form>
      {mutationRequests.length > 0 ? (
        <section className="mutation-list" aria-label="Meine Mutationen">
          <h3>Meine Mutationen</h3>
          {mutationRequests.map((mutationRequest) => (
            <div key={mutationRequest.id}>
              <p>{mutationRequest.quarter}</p>
              <p>Status: {mutationRequest.status}</p>
              <p>Wirksam ab: {mutationRequest.effective_date}</p>
            </div>
          ))}
        </section>
      ) : null}
    </section>
  );

  const adminMutationInbox = (
    <section className="admin-mutation-inbox" aria-label="Offene Mutationen">
      <h3>Offene Mutationen</h3>
      {adminMutationRequests.length > 0 ? (
        <div className="admin-mutation-list">
          {adminMutationRequests.map((mutationRequest) => (
            <div className="admin-mutation-item" key={mutationRequest.id}>
              <p>{mutationRequest.participant.display_name}</p>
              <p>{mutationRequest.participant.email}</p>
              <p>{mutationRequest.quarter}</p>
              <p>
                {mutationRequest.new_address.street},{" "}
                {mutationRequest.new_address.postal_code}{" "}
                {mutationRequest.new_address.city}
              </p>
              <p>Status: {mutationRequest.status}</p>
              {mutationRequest.review_reason ? (
                <p>{mutationRequest.review_reason}</p>
              ) : null}
              <div className="review-actions">
                <button
                  type="button"
                  disabled={mutationRequest.status !== "submitted"}
                  onClick={() =>
                    void reviewAdminMutationRequest(
                      mutationRequest.id,
                      "approved",
                    )
                  }
                >
                  Genehmigen
                </button>
                <label>
                  Ablehnungsgrund
                  <input
                    type="text"
                    value={reviewReasons[mutationRequest.id] ?? ""}
                    disabled={mutationRequest.status !== "submitted"}
                    onChange={(event) =>
                      setReviewReasons((current) => ({
                        ...current,
                        [mutationRequest.id]: event.target.value,
                      }))
                    }
                  />
                </label>
                <button
                  type="button"
                  disabled={mutationRequest.status !== "submitted"}
                  onClick={() =>
                    void reviewAdminMutationRequest(
                      mutationRequest.id,
                      "rejected",
                    )
                  }
                >
                  Ablehnen
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p>Keine offenen Mutationen</p>
      )}
      {adminMutationError ? (
        <div className="mutation-error" role="alert">
          <p>{adminMutationError}</p>
        </div>
      ) : null}
    </section>
  );

  const adminMutationPackages = (
    <section className="admin-mutation-packages" aria-label="Mutationspakete">
      <h3>Mutationspakete</h3>
      <form className="invitation-form mutation-package-form" onSubmit={createMutationPackage}>
        <label>
          Paketquartal
          <select
            value={packageQuarter}
            onChange={(event) => setPackageQuarter(event.target.value)}
          >
            <option value="2026-Q1">2026-Q1</option>
            <option value="2026-Q2">2026-Q2</option>
            <option value="2026-Q3">2026-Q3</option>
            <option value="2026-Q4">2026-Q4</option>
          </select>
        </label>
        <button type="submit">Paket erstellen</button>
        {mutationPackageError ? (
          <div className="mutation-error" role="alert">
            <p>{mutationPackageError}</p>
          </div>
        ) : null}
      </form>
      {mutationPackage ? (
        <div
          className="mutation-package-result"
          aria-label="Erstelltes Mutationspaket"
        >
          <p>Paket {mutationPackage.package_id}</p>
          <p>{mutationPackage.quarter}</p>
          <p>Wirksam ab: {mutationPackage.effective_date}</p>
          <p>Hash {mutationPackage.hash}</p>
          <p>Generiert: {mutationPackage.generated_at}</p>
          <div className="mutation-package-links">
            <button
              type="button"
              onClick={() =>
                void downloadMutationPackageArtifact(
                  mutationPackage.package_id,
                  "json",
                )
              }
            >
              JSON
            </button>
            <button
              type="button"
              onClick={() =>
                void downloadMutationPackageArtifact(
                  mutationPackage.package_id,
                  "csv",
                )
              }
            >
              CSV
            </button>
            <button
              type="button"
              onClick={() =>
                void downloadMutationPackageArtifact(
                  mutationPackage.package_id,
                  "pdf",
                )
              }
            >
              PDF
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );

  return (
    <main className="portal-shell">
      <section className="hero-band" aria-labelledby="portal-title">
        <p className="eyebrow">SunTerra LEG Basadingen</p>
        <h1 id="portal-title">SunTerra LEG Portal</h1>
        <p className="subtitle">Mitglieder- und Mutationsportal</p>
      </section>

      <section className="status-panel" aria-label="Systemstatus">
        <span
          className={`status-dot status-dot--${backend.kind}`}
          aria-hidden="true"
        />
        <div>
          <p className="status-label">
            {backend.kind === "connected"
              ? "Backend verbunden"
              : backend.kind === "offline"
                ? "Backend nicht erreichbar"
                : "Verbindung wird geprüft"}
          </p>
          {backend.kind === "connected" ? (
            <p className="status-detail">
              {backend.health.service} {backend.health.version}
            </p>
          ) : backend.kind === "offline" ? (
            <p className="status-detail">Die Portaloberfläche ist geladen.</p>
          ) : null}
        </div>
      </section>

      <section className="workspace-panel" aria-label="Geschützter Arbeitsbereich">
        {participantMembership ? (
          <div className="membership-workspace">
            <h2>Mein Mitgliederbereich</h2>
            <p>{participantMembership.display_name}</p>
            <dl className="membership-details">
              <div>
                <dt>E-Mail</dt>
                <dd>{participantMembership.email}</dd>
              </div>
              <div>
                <dt>LEG</dt>
                <dd>{participantMembership.leg_name}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>Mitgliedschaft aktiv</dd>
              </div>
            </dl>
            <p className="billing-notice">
              {participantMembership.billing_notice}
            </p>
            {emailVerification ? (
              <div className="invitation-result" role="status">
                <p>E-Mail verifiziert</p>
                <p>{emailVerification.participant_id}</p>
              </div>
            ) : null}
            {documentConsentForm}
            {contactChannelForm}
            {addressMutationForm}
          </div>
        ) : session.kind === "authenticated" && activeWorkspace ? (
          <div>
            <h2>{activeWorkspace.workspaceTitle}</h2>
            <p>{session.user.display_name}</p>
            {session.user.role === "leg_admin" ? (
              <>
                <form
                  className="invitation-form"
                  onSubmit={createParticipantInvitation}
                >
                  <label>
                    E-Mail
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(event) => setInviteEmail(event.target.value)}
                      required
                    />
                  </label>
                  <label>
                    Anzeigename
                    <input
                      type="text"
                      value={inviteDisplayName}
                      onChange={(event) =>
                        setInviteDisplayName(event.target.value)
                      }
                      required
                    />
                  </label>
                  <button type="submit">Einladung erstellen</button>
                  {participantInvitation ? (
                    <div className="invitation-result" role="status">
                      <p>Einladung erstellt</p>
                      <p>{participantInvitation.display_name}</p>
                      <p>{participantInvitation.token}</p>
                    </div>
                  ) : null}
                </form>
                {adminMutationInbox}
                {adminMutationPackages}
              </>
            ) : null}
            {session.user.role === "platform_admin" ? (
              <form
                className="invitation-form document-version-form"
                onSubmit={publishDocumentVersion}
              >
                <label>
                  Titel
                  <input
                    type="text"
                    value={documentTitle}
                    onChange={(event) => setDocumentTitle(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Version
                  <input
                    type="text"
                    value={documentVersion}
                    onChange={(event) =>
                      setDocumentVersion(event.target.value)
                    }
                    required
                  />
                </label>
                <label>
                  Inhalt
                  <textarea
                    value={documentContent}
                    onChange={(event) =>
                      setDocumentContent(event.target.value)
                    }
                    required
                  />
                </label>
                <button type="submit">Dokumentversion veröffentlichen</button>
                {publishedDocumentVersion ? (
                  <div className="invitation-result" role="status">
                    <p>Dokumentversion veröffentlicht</p>
                    <p>{publishedDocumentVersion.version}</p>
                    <p>{publishedDocumentVersion.document_hash}</p>
                  </div>
                ) : null}
              </form>
            ) : null}
            {session.user.role === "participant" ? (
              <>
                {documentConsentForm}
                {contactChannelForm}
                {addressMutationForm}
              </>
            ) : null}
          </div>
        ) : (
          <>
            <div>
              <h2>Anmeldung erforderlich</h2>
              <p>Wähle für die lokale Entwicklung eine Demo-Rolle.</p>
            </div>
            <div className="role-actions" aria-label="Demo-Rollen">
              {demoRoles.map((demoRole) => (
                <button
                  key={demoRole.role}
                  type="button"
                  onClick={() => loginAs(demoRole.role)}
                >
                  {demoRole.label}
                </button>
              ))}
            </div>
            <form
              className="invitation-form"
              onSubmit={acceptParticipantInvitation}
            >
              <label>
                Einladungstoken
                <input
                  type="text"
                  value={onboardingToken}
                  onChange={(event) => setOnboardingToken(event.target.value)}
                  required
                />
              </label>
              <button type="submit">Einladung annehmen und verifizieren</button>
              {emailVerification ? (
                <div className="invitation-result" role="status">
                  <p>E-Mail verifiziert</p>
                  <p>{emailVerification.participant_id}</p>
                </div>
              ) : null}
            </form>
          </>
        )}
      </section>
    </main>
  );
}
