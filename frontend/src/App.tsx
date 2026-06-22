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

type IdentityCheckpoint = {
  required_level: "email_verified";
  current_level: "unverified" | "email_verified";
  satisfied: boolean;
};

type SelfServiceOnboardingResponse = {
  access_token: string;
  token_type: "bearer";
  participant_id: string;
  participant_status: "pending_email_verification";
  identity_checkpoint: IdentityCheckpoint;
  dev_email_verification_token: string;
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

type MutationMode = "regular" | "special";

type RegularMutationType =
  | "address"
  | "meter_point"
  | "role"
  | "generation_asset"
  | "entry"
  | "exit";

type SpecialMutationType =
  | "move_out"
  | "death"
  | "owner_tenant_change"
  | "meter_point_error"
  | "municipality_utility_correction";

type MutationType = RegularMutationType | SpecialMutationType;

type MutationDetails = Record<string, string | number>;

type MutationRequest = {
  id: string;
  participant_id: string;
  leg_id: "basadingen";
  mutation_type: MutationType;
  mode: MutationMode;
  status: "submitted" | "approved" | "rejected";
  quarter: string | null;
  quarter_end: string | null;
  participant_deadline: string | null;
  effective_date: string;
  submitted_at: string;
  reviewed_at: string | null;
  review_reason: string | null;
  new_address: {
    street: string;
    postal_code: string;
    city: string;
    country: string;
  } | null;
  mutation_details: MutationDetails;
  audit_events: AuditEvent[];
};

type AdminMutationRequest = MutationRequest & {
  participant: {
    participant_id: string;
    display_name: string;
    email: string;
  };
};

type FileEvidence = {
  id: string;
  mutation_request_id: string;
  participant_id: string;
  document_type: "mutation_review_supporting_document";
  purpose: "mutation_review";
  version: string;
  filename: string;
  content_type: string;
  sha256_hash: string;
  access_protection: string;
  retention_status: string;
  created_at: string;
};

type FileEvidenceDraft = {
  version: string;
  filename: string;
  contentType: string;
  content: string;
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
    mutation_type: MutationType;
    mode: "regular";
    effective_date: string;
    new_address: {
      street: string;
      postal_code: string;
      city: string;
      country: string;
    } | null;
    mutation_details: MutationDetails;
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

type PartnerPackageStatus =
  | "created"
  | "received"
  | "in_review"
  | "processed"
  | "question"
  | "technically_not_possible";

type PartnerPackageStatusUpdate = Exclude<PartnerPackageStatus, "created">;

type PartnerMutationPackageSummary = {
  package_id: string;
  leg_id: "basadingen";
  quarter: string;
  effective_date: string;
  generated_at: string;
  record_count: number;
  current_status: PartnerPackageStatus;
  status_updated_at: string;
};

type PartnerMutationPackageStatusEvent = {
  status: PartnerPackageStatus;
  actor_role: Role;
  created_at: string;
  reference: string | null;
  reason: string | null;
};

type PartnerMutationPackageDetail = PartnerMutationPackageSummary & {
  records: MutationPackage["records"];
  status_history: PartnerMutationPackageStatusEvent[];
};

type PartnerMutationPackageStatusRead = {
  package_id: string;
  current_status: PartnerPackageStatus;
  status_history: PartnerMutationPackageStatusEvent[];
};

type PartnerMemberRegister = {
  leg_id: "basadingen";
  leg_name: string;
  members: Array<{
    participant_id: string;
    display_name: string;
    membership_status: string;
    reporting_address: {
      street: string;
      postal_code: string;
      city: string;
      country: string;
    } | null;
    latest_package_status: {
      package_id: string;
      quarter: string;
      effective_date: string;
      status: PartnerPackageStatus;
    };
  }>;
};

type PartnerStatusDraft = {
  status: PartnerPackageStatusUpdate;
  reference: string;
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
const emptyFileEvidenceDraft: FileEvidenceDraft = {
  version: "",
  filename: "",
  contentType: "text/plain",
  content: "",
};
const regularMutationTypeOptions: Array<{
  value: RegularMutationType;
  label: string;
}> = [
  { value: "address", label: "Adressmutation" },
  { value: "meter_point", label: "Messpunktmutation" },
  { value: "role", label: "Rollenmutation" },
  { value: "generation_asset", label: "Erzeugungsanlage" },
  { value: "entry", label: "Eintritt" },
  { value: "exit", label: "Austritt" },
];
const specialMutationTypeOptions: Array<{
  value: SpecialMutationType;
  label: string;
}> = [
  { value: "move_out", label: "Auszug" },
  { value: "death", label: "Todesfall" },
  { value: "owner_tenant_change", label: "Eigentuemer-/Mieterwechsel" },
  { value: "meter_point_error", label: "Messpunktfehler" },
  {
    value: "municipality_utility_correction",
    label: "Gemeinde-/EW-Korrektur",
  },
];
const roleOptions = [
  { value: "owner", label: "Eigentuemer" },
  { value: "tenant", label: "Mieter" },
  { value: "producer", label: "Produzent" },
  { value: "prosumer", label: "Prosumer" },
];

function textToBase64(value: string) {
  const bytes = new TextEncoder().encode(value);
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");

  return window.btoa(binary);
}

function mutationTypeLabel(mutationType: MutationType) {
  return (
    regularMutationTypeOptions.find((option) => option.value === mutationType)
      ?.label ??
    specialMutationTypeOptions.find((option) => option.value === mutationType)
      ?.label ??
    mutationType
  );
}

function isSpecialMutationType(
  mutationType: MutationType,
): mutationType is SpecialMutationType {
  return specialMutationTypeOptions.some((option) => option.value === mutationType);
}

function requestedRoleLabel(value: string | number | undefined) {
  return (
    roleOptions.find((option) => option.value === value)?.label ??
    String(value ?? "")
  );
}

function addressLine(address: MutationRequest["new_address"]) {
  return address
    ? `${address.street}, ${address.postal_code} ${address.city}, ${address.country}`
    : "Keine Adresse";
}

function mutationDetailLines(
  mutationType: MutationType,
  details: MutationDetails,
  newAddress: MutationRequest["new_address"],
) {
  if (isSpecialMutationType(mutationType)) {
    return [
      `Grund: ${details.reason ?? ""}`,
      `Ereignisdatum: ${details.event_date ?? ""}`,
    ];
  }
  if (mutationType === "address") {
    return [`Adresse: ${addressLine(newAddress)}`];
  }
  if (mutationType === "meter_point") {
    return [`Messpunkt: ${details.metering_code ?? ""}`];
  }
  if (mutationType === "role") {
    return [`Rolle: ${requestedRoleLabel(details.requested_role)}`];
  }
  if (mutationType === "generation_asset") {
    return [
      (
        `Erzeugungsanlage: ${details.technology ?? ""}, ` +
        `${details.installed_capacity_kw ?? ""} kW, ` +
        `Inbetriebnahme ${details.commissioned_on ?? ""}`
      ),
    ];
  }
  return [`Grund: ${details.reason ?? ""}`];
}

export function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });
  const [session, setSession] = useState<SessionState>({ kind: "anonymous" });
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [participantInvitation, setParticipantInvitation] =
    useState<ParticipantInvitation | null>(null);
  const [onboardingToken, setOnboardingToken] = useState("");
  const [selfServiceEmail, setSelfServiceEmail] = useState("");
  const [selfServiceDisplayName, setSelfServiceDisplayName] = useState("");
  const [selfServiceOnboarding, setSelfServiceOnboarding] =
    useState<SelfServiceOnboardingResponse | null>(null);
  const [identityCheckpoint, setIdentityCheckpoint] =
    useState<IdentityCheckpoint | null>(null);
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
  const [mutationMode, setMutationMode] = useState<MutationMode>("regular");
  const [mutationType, setMutationType] = useState<MutationType>("address");
  const [mutationQuarter, setMutationQuarter] = useState("2026-Q3");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressPostalCode, setAddressPostalCode] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressCountry, setAddressCountry] = useState("CH");
  const [meteringCode, setMeteringCode] = useState("");
  const [requestedRole, setRequestedRole] = useState("owner");
  const [generationTechnology, setGenerationTechnology] = useState("");
  const [installedCapacityKw, setInstalledCapacityKw] = useState("");
  const [commissionedOn, setCommissionedOn] = useState("");
  const [mutationReason, setMutationReason] = useState("");
  const [mutationEventDate, setMutationEventDate] = useState("");
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
  const [fileEvidenceDrafts, setFileEvidenceDrafts] = useState<
    Record<string, FileEvidenceDraft>
  >({});
  const [fileEvidenceByMutationId, setFileEvidenceByMutationId] = useState<
    Record<string, FileEvidence[]>
  >({});
  const [packageQuarter, setPackageQuarter] = useState("2026-Q3");
  const [mutationPackage, setMutationPackage] =
    useState<MutationPackage | null>(null);
  const [mutationPackageError, setMutationPackageError] = useState("");
  const [partnerPackages, setPartnerPackages] = useState<
    PartnerMutationPackageSummary[]
  >([]);
  const [partnerPackageDetails, setPartnerPackageDetails] = useState<
    Record<string, PartnerMutationPackageDetail>
  >({});
  const [partnerStatusDrafts, setPartnerStatusDrafts] = useState<
    Record<string, PartnerStatusDraft>
  >({});
  const [partnerPackageError, setPartnerPackageError] = useState("");
  const [partnerMemberRegister, setPartnerMemberRegister] =
    useState<PartnerMemberRegister | null>(null);
  const [partnerMemberRegisterError, setPartnerMemberRegisterError] =
    useState("");

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
    if (user.role === "partner_admin") {
      void loadPartnerMutationPackages(token);
      void loadPartnerMemberRegister(token);
    } else {
      setPartnerPackages([]);
      setPartnerPackageDetails({});
      setPartnerMemberRegister(null);
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

  async function startSelfServiceOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const response = await fetch(
      `${apiBaseUrl}/api/auth/self-service-onboarding-requests`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: selfServiceEmail,
          display_name: selfServiceDisplayName,
        }),
      },
    );

    if (response.ok) {
      const onboarding =
        (await response.json()) as SelfServiceOnboardingResponse;
      setSelfServiceOnboarding(onboarding);
      setIdentityCheckpoint(onboarding.identity_checkpoint);
    }
  }

  async function verifySelfServiceEmail() {
    if (selfServiceOnboarding === null) {
      return;
    }

    const verifyResponse = await fetch(
      (
        `${apiBaseUrl}/api/auth/email-verifications/` +
        `${selfServiceOnboarding.dev_email_verification_token}/verify`
      ),
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

    const checkpointResponse = await fetch(
      (
        `${apiBaseUrl}/api/participants/me/identity-checkpoint` +
        "?action=membership_activation"
      ),
      {
        headers: {
          Authorization: `Bearer ${selfServiceOnboarding.access_token}`,
        },
      },
    );

    if (checkpointResponse.ok) {
      const checkpoint = (await checkpointResponse.json()) as IdentityCheckpoint;
      setIdentityCheckpoint(checkpoint);
    }

    const membershipResponse = await fetch(
      `${apiBaseUrl}/api/participants/me/membership`,
      {
        headers: {
          Authorization: `Bearer ${selfServiceOnboarding.access_token}`,
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
        token: selfServiceOnboarding.access_token,
        user: {
          id: participantMembership.participant_id,
          email: participantMembership.email,
          display_name: participantMembership.display_name,
          role: "participant",
        },
      });
      void loadCurrentDocument(selfServiceOnboarding.access_token);
      void loadContactChannels(selfServiceOnboarding.access_token);
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

  async function loadPartnerMutationPackages(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/partner/mutation-packages`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const packages = (await response.json()) as PartnerMutationPackageSummary[];
      setPartnerPackages(packages);
    }
  }

  async function loadPartnerMemberRegister(token: string) {
    setPartnerMemberRegisterError("");
    const response = await fetch(`${apiBaseUrl}/api/partner/member-register`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const register = (await response.json()) as Partial<PartnerMemberRegister>;
      if (
        register.leg_id === "basadingen" &&
        typeof register.leg_name === "string" &&
        Array.isArray(register.members)
      ) {
        setPartnerMemberRegister(register as PartnerMemberRegister);
      }
      return;
    }

    setPartnerMemberRegisterError("Mitgliederregister konnte nicht geladen werden");
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

  function updateFileEvidenceDraft(
    mutationRequestId: string,
    changes: Partial<FileEvidenceDraft>,
  ) {
    setFileEvidenceDrafts((current) => ({
      ...current,
      [mutationRequestId]: {
        ...emptyFileEvidenceDraft,
        ...(current[mutationRequestId] ?? {}),
        ...changes,
      },
    }));
  }

  async function attachMutationFileEvidence(
    event: FormEvent<HTMLFormElement>,
    mutationRequestId: string,
  ) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const draft = fileEvidenceDrafts[mutationRequestId] ?? emptyFileEvidenceDraft;
    setAdminMutationError("");
    const response = await fetch(
      `${apiBaseUrl}/api/admin/mutation-requests/${mutationRequestId}/file-evidence`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          document_type: "mutation_review_supporting_document",
          purpose: "mutation_review",
          version: draft.version,
          filename: draft.filename,
          content_type: draft.contentType,
          content_base64: textToBase64(draft.content),
        }),
      },
    );

    if (response.ok) {
      const evidence = (await response.json()) as FileEvidence;
      setFileEvidenceByMutationId((current) => ({
        ...current,
        [mutationRequestId]: [
          ...(current[mutationRequestId] ?? []),
          evidence,
        ],
      }));
      setFileEvidenceDrafts((current) => ({
        ...current,
        [mutationRequestId]: {
          ...emptyFileEvidenceDraft,
          version: draft.version,
          contentType: draft.contentType,
        },
      }));
      return;
    }

    const error = (await response.json()) as { detail?: string };
    setAdminMutationError(
      error.detail ?? "Datei-Nachweis konnte nicht gespeichert werden",
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

  async function loadPartnerPackageDetail(packageId: string) {
    if (session.kind !== "authenticated") {
      return;
    }

    setPartnerPackageError("");
    const response = await fetch(
      `${apiBaseUrl}/api/partner/mutation-packages/${packageId}`,
      {
        headers: {
          Authorization: `Bearer ${session.token}`,
        },
      },
    );

    if (response.ok) {
      const detail = (await response.json()) as PartnerMutationPackageDetail;
      setPartnerPackageDetails((current) => ({
        ...current,
        [packageId]: detail,
      }));
      setPartnerStatusDrafts((current) => ({
        ...current,
        [packageId]: current[packageId] ?? {
          status: "received",
          reference: "",
        },
      }));
      return;
    }

    setPartnerPackageError("Mutationspaket konnte nicht geladen werden");
  }

  async function updatePartnerPackageStatus(
    event: FormEvent<HTMLFormElement>,
    packageId: string,
  ) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const draft = partnerStatusDrafts[packageId] ?? {
      status: "received",
      reference: "",
    };
    const reference = draft.reference.trim();
    setPartnerPackageError("");
    const response = await fetch(
      `${apiBaseUrl}/api/partner/mutation-packages/${packageId}/status`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          status: draft.status,
          ...(reference ? { reference } : {}),
        }),
      },
    );

    if (response.ok) {
      const statusRead =
        (await response.json()) as PartnerMutationPackageStatusRead;
      const latestStatus = statusRead.status_history.at(-1);
      setPartnerPackages((current) =>
        current.map((mutationPackage) =>
          mutationPackage.package_id === packageId
            ? {
                ...mutationPackage,
                current_status: statusRead.current_status,
                status_updated_at:
                  latestStatus?.created_at ?? mutationPackage.status_updated_at,
              }
            : mutationPackage,
        ),
      );
      setPartnerPackageDetails((current) => {
        const detail = current[packageId];
        if (!detail) {
          return current;
        }

        return {
          ...current,
          [packageId]: {
            ...detail,
            current_status: statusRead.current_status,
            status_updated_at:
              latestStatus?.created_at ?? detail.status_updated_at,
            status_history: statusRead.status_history,
          },
        };
      });
      return;
    }

    const error = (await response.json()) as { detail?: string };
    setPartnerPackageError(
      error.detail ?? "Paketstatus konnte nicht aktualisiert werden",
    );
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

  async function submitMutation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const mutationPayload: Record<string, unknown> = {
      mutation_type: mutationType,
      mode: mutationMode,
    };
    if (mutationMode === "special") {
      mutationPayload.event_date = mutationEventDate;
      mutationPayload.reason = mutationReason;
    }
    if (mutationMode === "regular") {
      mutationPayload.requested_quarter = mutationQuarter;
    }
    if (mutationMode === "regular" && mutationType === "address") {
      mutationPayload.new_address = {
        street: addressStreet,
        postal_code: addressPostalCode,
        city: addressCity,
        country: addressCountry,
      };
    }
    if (mutationMode === "regular" && mutationType === "meter_point") {
      mutationPayload.metering_code = meteringCode;
    }
    if (mutationMode === "regular" && mutationType === "role") {
      mutationPayload.requested_role = requestedRole;
    }
    if (mutationMode === "regular" && mutationType === "generation_asset") {
      mutationPayload.technology = generationTechnology;
      mutationPayload.installed_capacity_kw = Number(installedCapacityKw);
      mutationPayload.commissioned_on = commissionedOn;
    }
    if (
      mutationMode === "regular" &&
      (mutationType === "entry" || mutationType === "exit")
    ) {
      mutationPayload.reason = mutationReason;
    }

    setMutationError("");
    const response = await fetch(`${apiBaseUrl}/api/participants/me/mutation-requests`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(mutationPayload),
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
    <section className="address-mutations" aria-label="Meldepflichtige Mutation">
      <form className="invitation-form address-mutation-form" onSubmit={submitMutation}>
        <h3>
          {mutationMode === "special"
            ? "Sondermutation"
            : mutationTypeLabel(mutationType)}
        </h3>
        <label>
          Mutationsmodus
          <select
            value={mutationMode}
            onChange={(event) => {
              const nextMode = event.target.value as MutationMode;
              setMutationMode(nextMode);
              setMutationType(nextMode === "special" ? "move_out" : "address");
            }}
          >
            <option value="regular">Regulaere Quartalsmutation</option>
            <option value="special">Sondermutation</option>
          </select>
        </label>
        <label>
          {mutationMode === "special" ? "Sondermutationstyp" : "Mutationstyp"}
          <select
            value={mutationType}
            onChange={(event) =>
              setMutationType(event.target.value as MutationType)
            }
          >
            {(mutationMode === "special"
              ? specialMutationTypeOptions
              : regularMutationTypeOptions
            ).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        {mutationMode === "regular" ? (
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
        ) : null}
        {mutationMode === "regular" && mutationType === "address" ? (
          <>
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
          </>
        ) : null}
        {mutationMode === "regular" && mutationType === "meter_point" ? (
          <label>
            Messpunktcode
            <input
              type="text"
              value={meteringCode}
              onChange={(event) => setMeteringCode(event.target.value)}
              required
            />
          </label>
        ) : null}
        {mutationMode === "regular" && mutationType === "role" ? (
          <label>
            Gewuenschte Rolle
            <select
              value={requestedRole}
              onChange={(event) => setRequestedRole(event.target.value)}
            >
              {roleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {mutationMode === "regular" && mutationType === "generation_asset" ? (
          <>
            <label>
              Technologie
              <input
                type="text"
                value={generationTechnology}
                onChange={(event) => setGenerationTechnology(event.target.value)}
                required
              />
            </label>
            <label>
              Installierte Leistung kW
              <input
                type="number"
                min="0"
                step="0.1"
                value={installedCapacityKw}
                onChange={(event) => setInstalledCapacityKw(event.target.value)}
                required
              />
            </label>
            <label>
              Inbetriebnahme
              <input
                type="date"
                value={commissionedOn}
                onChange={(event) => setCommissionedOn(event.target.value)}
                required
              />
            </label>
          </>
        ) : null}
        {mutationMode === "regular" &&
        (mutationType === "entry" || mutationType === "exit") ? (
          <label>
            Grund
            <input
              type="text"
              value={mutationReason}
              onChange={(event) => setMutationReason(event.target.value)}
              required
            />
          </label>
        ) : null}
        {mutationMode === "special" ? (
          <>
            <label>
              Ereignisdatum
              <input
                type="date"
                value={mutationEventDate}
                onChange={(event) => setMutationEventDate(event.target.value)}
                required
              />
            </label>
            <label>
              Begruendung
              <input
                type="text"
                value={mutationReason}
                onChange={(event) => setMutationReason(event.target.value)}
                required
              />
            </label>
          </>
        ) : null}
        <button type="submit">
          {mutationMode === "special"
            ? "Sondermutation einreichen"
            : mutationType === "address"
              ? "Adressmutation einreichen"
            : "Mutation einreichen"}
        </button>
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
            <div
              className={`mutation-list-item mutation-list-item--${mutationRequest.mode}`}
              key={mutationRequest.id}
            >
              <p className="mutation-mode-badge">
                {mutationRequest.mode === "special"
                  ? "Sondermutation"
                  : "Regulaere Mutation"}
              </p>
              <p>{mutationTypeLabel(mutationRequest.mutation_type)}</p>
              <p>{mutationRequest.quarter ?? "Kein regulaeres Quartal"}</p>
              {mutationDetailLines(
                mutationRequest.mutation_type,
                mutationRequest.mutation_details,
                mutationRequest.new_address,
              ).map((line) => (
                <p key={line}>{line}</p>
              ))}
              <p>Status: {mutationRequest.status}</p>
              {mutationRequest.participant_deadline ? (
                <p>Teilnehmerfrist: {mutationRequest.participant_deadline}</p>
              ) : null}
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
            <div
              className={`admin-mutation-item admin-mutation-item--${mutationRequest.mode}`}
              key={mutationRequest.id}
            >
              <p>{mutationRequest.participant.display_name}</p>
              <p>{mutationRequest.participant.email}</p>
              <p className="mutation-mode-badge">
                {mutationRequest.mode === "special"
                  ? "Sondermutation"
                  : "Regulaere Mutation"}
              </p>
              <p>{mutationTypeLabel(mutationRequest.mutation_type)}</p>
              <p>{mutationRequest.quarter ?? "Kein regulaeres Quartal"}</p>
              {mutationDetailLines(
                mutationRequest.mutation_type,
                mutationRequest.mutation_details,
                mutationRequest.new_address,
              ).map((line) => (
                <p key={line}>{line}</p>
              ))}
              <p>Status: {mutationRequest.status}</p>
              {mutationRequest.participant_deadline ? (
                <p>Teilnehmerfrist: {mutationRequest.participant_deadline}</p>
              ) : null}
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
              <section className="file-evidence" aria-label="Datei-Nachweise">
                <h4>Datei-Nachweise</h4>
                <form
                  className="file-evidence-form"
                  onSubmit={(event) =>
                    void attachMutationFileEvidence(event, mutationRequest.id)
                  }
                >
                  <label>
                    Nachweisversion
                    <input
                      type="text"
                      value={
                        fileEvidenceDrafts[mutationRequest.id]?.version ?? ""
                      }
                      onChange={(event) =>
                        updateFileEvidenceDraft(mutationRequest.id, {
                          version: event.target.value,
                        })
                      }
                      required
                    />
                  </label>
                  <label>
                    Dateiname
                    <input
                      type="text"
                      value={
                        fileEvidenceDrafts[mutationRequest.id]?.filename ?? ""
                      }
                      onChange={(event) =>
                        updateFileEvidenceDraft(mutationRequest.id, {
                          filename: event.target.value,
                        })
                      }
                      required
                    />
                  </label>
                  <label>
                    MIME-Typ
                    <input
                      type="text"
                      value={
                        fileEvidenceDrafts[mutationRequest.id]?.contentType ??
                        "text/plain"
                      }
                      onChange={(event) =>
                        updateFileEvidenceDraft(mutationRequest.id, {
                          contentType: event.target.value,
                        })
                      }
                      required
                    />
                  </label>
                  <label>
                    Dateiinhalt
                    <textarea
                      value={
                        fileEvidenceDrafts[mutationRequest.id]?.content ?? ""
                      }
                      onChange={(event) =>
                        updateFileEvidenceDraft(mutationRequest.id, {
                          content: event.target.value,
                        })
                      }
                      required
                    />
                  </label>
                  <button type="submit">Nachweis hochladen</button>
                </form>
                {(fileEvidenceByMutationId[mutationRequest.id] ?? []).map(
                  (evidence) => (
                    <div className="file-evidence-result" key={evidence.id}>
                      <p>{evidence.filename}</p>
                      <p>Version {evidence.version}</p>
                      <p>Hash {evidence.sha256_hash}</p>
                      <p>{evidence.access_protection}</p>
                      <p>{evidence.retention_status}</p>
                    </div>
                  ),
                )}
              </section>
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

  const partnerPackageInbox = (
    <section className="partner-package-inbox" aria-label="Mutationspaket-Eingang">
      <h3>Mutationspaket-Eingang</h3>
      {partnerPackages.length > 0 ? (
        <div className="partner-package-list">
          {partnerPackages.map((mutationPackage) => {
            const detail = partnerPackageDetails[mutationPackage.package_id];
            const draft = partnerStatusDrafts[mutationPackage.package_id] ?? {
              status: "received",
              reference: "",
            };

            return (
              <div className="partner-package-item" key={mutationPackage.package_id}>
                <p>Paket {mutationPackage.package_id}</p>
                <p>{mutationPackage.quarter}</p>
                <p>Wirksam ab: {mutationPackage.effective_date}</p>
                <p>{mutationPackage.record_count} Mutation</p>
                <p>Status: {mutationPackage.current_status}</p>
                <button
                  type="button"
                  onClick={() =>
                    void loadPartnerPackageDetail(mutationPackage.package_id)
                  }
                >
                  Details anzeigen
                </button>
                {detail ? (
                  <div className="partner-package-detail">
                    {detail.records.map((record) => (
                      <div key={record.mutation_request_id}>
                        <p>{record.mutation_request_id}</p>
                        <p>{record.participant_id}</p>
                        <p>{mutationTypeLabel(record.mutation_type)}</p>
                        {mutationDetailLines(
                          record.mutation_type,
                          record.mutation_details,
                          record.new_address,
                        ).map((line) => (
                          <p key={line}>{line}</p>
                        ))}
                        {record.new_address ? (
                          <p>{addressLine(record.new_address)}</p>
                        ) : null}
                      </div>
                    ))}
                    <div className="partner-status-history">
                      {detail.status_history.map((statusEvent) => (
                        <div
                          key={`${statusEvent.status}-${statusEvent.created_at}`}
                        >
                          <p>Status: {statusEvent.status}</p>
                          <p>{statusEvent.actor_role}</p>
                          <p>{statusEvent.created_at}</p>
                          {statusEvent.reference ? (
                            <p>{statusEvent.reference}</p>
                          ) : null}
                          {statusEvent.reason ? <p>{statusEvent.reason}</p> : null}
                        </div>
                      ))}
                    </div>
                    <form
                      className="partner-status-form"
                      onSubmit={(event) =>
                        void updatePartnerPackageStatus(
                          event,
                          mutationPackage.package_id,
                        )
                      }
                    >
                      <label>
                        Paketstatus
                        <select
                          value={draft.status}
                          onChange={(event) =>
                            setPartnerStatusDrafts((current) => ({
                              ...current,
                              [mutationPackage.package_id]: {
                                ...draft,
                                status: event.target
                                  .value as PartnerPackageStatusUpdate,
                              },
                            }))
                          }
                        >
                          <option value="received">Empfangen</option>
                          <option value="in_review">In Prüfung</option>
                          <option value="processed">Verarbeitet</option>
                          <option value="question">Rückfrage</option>
                          <option value="technically_not_possible">
                            Technisch nicht möglich
                          </option>
                        </select>
                      </label>
                      <label>
                        Referenz oder Grund
                        <input
                          type="text"
                          value={draft.reference}
                          onChange={(event) =>
                            setPartnerStatusDrafts((current) => ({
                              ...current,
                              [mutationPackage.package_id]: {
                                ...draft,
                                reference: event.target.value,
                              },
                            }))
                          }
                        />
                      </label>
                      <button type="submit">Status aktualisieren</button>
                    </form>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : (
        <p>Keine Mutationspakete</p>
      )}
      {partnerPackageError ? (
        <div className="mutation-error" role="alert">
          <p>{partnerPackageError}</p>
        </div>
      ) : null}
    </section>
  );

  const partnerMemberRegisterView = (
    <section className="partner-member-register" aria-label="Mitgliederregister">
      <h3>Mitgliederregister</h3>
      {partnerMemberRegister ? (
        <>
          <p>{partnerMemberRegister.leg_name}</p>
          {partnerMemberRegister.members.length > 0 ? (
            <div className="partner-member-list">
              {partnerMemberRegister.members.map((member) => (
                <div className="partner-member-item" key={member.participant_id}>
                  <p>{member.display_name}</p>
                  <p>Status: {member.membership_status}</p>
                  <p>{addressLine(member.reporting_address)}</p>
                  <p>Paket {member.latest_package_status.package_id}</p>
                  <p>{member.latest_package_status.quarter}</p>
                  <p>Wirksam ab: {member.latest_package_status.effective_date}</p>
                  <p>Paketstatus: {member.latest_package_status.status}</p>
                </div>
              ))}
            </div>
          ) : (
            <p>Keine Mitglieder</p>
          )}
        </>
      ) : (
        <p>Mitgliederregister wird geladen</p>
      )}
      {partnerMemberRegisterError ? (
        <div className="mutation-error" role="alert">
          <p>{partnerMemberRegisterError}</p>
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
            {session.user.role === "partner_admin" ? (
              <>
                {partnerMemberRegisterView}
                {partnerPackageInbox}
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
              className="invitation-form self-service-form"
              onSubmit={startSelfServiceOnboarding}
            >
              <label>
                Self-Service E-Mail
                <input
                  type="email"
                  value={selfServiceEmail}
                  onChange={(event) => setSelfServiceEmail(event.target.value)}
                  required
                />
              </label>
              <label>
                Self-Service Anzeigename
                <input
                  type="text"
                  value={selfServiceDisplayName}
                  onChange={(event) =>
                    setSelfServiceDisplayName(event.target.value)
                  }
                  required
                />
              </label>
              <button type="submit">Self-Service starten</button>
            </form>
            {selfServiceOnboarding && identityCheckpoint ? (
              <section
                className="identity-checkpoint"
                aria-label="Identitätsprüfung"
              >
                <h3>Identitätsprüfung</h3>
                <p>Erforderlich: {identityCheckpoint.required_level}</p>
                <p>Aktuell: {identityCheckpoint.current_level}</p>
                <p>
                  {identityCheckpoint.satisfied
                    ? "Checkpoint erfüllt"
                    : "Checkpoint offen"}
                </p>
                <p>{selfServiceOnboarding.dev_email_verification_token}</p>
                <button
                  type="button"
                  disabled={identityCheckpoint.satisfied}
                  onClick={() => void verifySelfServiceEmail()}
                >
                  Dev E-Mail verifizieren
                </button>
              </section>
            ) : null}
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
