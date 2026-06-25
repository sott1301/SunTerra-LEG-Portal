import { type FormEvent, useEffect, useState } from "react";

import type { components } from "./generated/api-types";
import "./styles.css";

type ApiSchemas = components["schemas"];

type HealthStatus = ApiSchemas["HealthStatus"];

type Role = ApiSchemas["Role"];

type PreferredContactChannel = "email" | "phone";

type CurrentUser = ApiSchemas["CurrentUser"];

type LoginRequest = ApiSchemas["LoginRequest"];

type ParticipantInvitation = ApiSchemas["ParticipantInvitationRead"];

type ParticipantInvitationCreate = ApiSchemas["ParticipantInvitationCreate"];

type InvitationAcceptResponse = ApiSchemas["InvitationAcceptResponse"];

type EmailVerificationResponse = ApiSchemas["EmailVerificationResponse"];

type IdentityCheckpoint = ApiSchemas["IdentityCheckpointRead"];

type SelfServiceOnboardingResponse = ApiSchemas["SelfServiceOnboardingResponse"];

type SelfServiceOnboardingCreate = ApiSchemas["SelfServiceOnboardingCreate"];

type InterestRecord = ApiSchemas["InterestRecordRead"];

type ParticipantAccountSetup = ApiSchemas["ParticipantAccountSetup"];

type AuthTokenResponse = ApiSchemas["AuthTokenResponse"];

type TotpEnrollmentResponse = ApiSchemas["TotpEnrollmentResponse"];

type UserAccount = ApiSchemas["UserAccountRead"];

type UserAccountCreate = ApiSchemas["UserAccountCreate"];

type UserPasswordReset = ApiSchemas["UserPasswordReset"];

type PasswordResetRequestCreate = ApiSchemas["PasswordResetRequestCreate"];

type PasswordResetConfirm = ApiSchemas["PasswordResetConfirm"];

type PasswordResetStatus = ApiSchemas["PasswordResetStatusRead"];

type PartnerAdminUserCreate = ApiSchemas["PartnerAdminUserCreate"];

type ParticipantMembership = ApiSchemas["ParticipantMembershipRead"];

type DocumentVersion = ApiSchemas["DocumentVersionRead"];

type DocumentVersionCreate = ApiSchemas["DocumentVersionCreate"];

type CurrentDocument = ApiSchemas["CurrentDocumentRead"];

type ConsentEvidenceCreate = ApiSchemas["ConsentEvidenceCreate"];

type ConsentEvidence = ApiSchemas["ConsentEvidenceRead"];

const REQUIRED_PARTICIPANT_DOCUMENT_KEYS = [
  "privacy_notice",
  "portal_terms",
  "leg_contract",
] as const;

function isCurrentDocument(value: Partial<CurrentDocument>): value is CurrentDocument {
  return (
    typeof value.id === "string" &&
    typeof value.document_key === "string" &&
    typeof value.title === "string" &&
    typeof value.version === "string" &&
    typeof value.content === "string" &&
    typeof value.document_hash === "string" &&
    typeof value.context === "string" &&
    typeof value.published_at === "string"
  );
}

type ParticipantContactChannels = ApiSchemas["ParticipantContactChannelsRead"];

type ParticipantContactChannelsUpdate =
  ApiSchemas["ParticipantContactChannelsUpdate"];

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

type MutationRequestCreate = ApiSchemas["MutationRequestCreate"];

type MutationRequest = ApiSchemas["ParticipantMutationRequestRead"];

type AdminMutationRequest = ApiSchemas["AdminMutationRequestRead"];

type MutationReviewDecision = ApiSchemas["MutationReviewDecision"];

type FileEvidence = ApiSchemas["FileEvidenceMetadataRead"];

type FileEvidenceCreate = ApiSchemas["FileEvidenceCreate"];

type FileEvidenceDraft = {
  version: string;
  filename: string;
  contentType: string;
  content: string;
};

type MutationPackageCreate = ApiSchemas["MutationPackageCreate"];

type MutationPackage = ApiSchemas["MutationPackageRead"];

type PartnerPackageStatus =
  | "created"
  | "received"
  | "in_review"
  | "processed"
  | "question"
  | "technically_not_possible";

type PartnerPackageStatusUpdate = Exclude<PartnerPackageStatus, "created">;

type MutationPackageStatusUpdate = ApiSchemas["MutationPackageStatusUpdate"];

type PartnerMutationPackageSummary =
  ApiSchemas["PartnerMutationPackageSummary"];

type PartnerMutationPackageDetail = ApiSchemas["PartnerMutationPackageDetail"];

type PartnerMutationPackageStatusRead =
  ApiSchemas["PartnerMutationPackageStatusRead"];

type PartnerMemberRegister = ApiSchemas["PartnerMemberRegisterRead"];

type PartnerTask = ApiSchemas["PartnerTaskRead"];

type PilotFeedbackCreate = ApiSchemas["PilotFeedbackCreate"];

type PilotFeedback = ApiSchemas["PilotFeedbackRead"];

type PilotFeedbackUpdate = ApiSchemas["PilotFeedbackUpdate"];

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
    workspaceTitle: "Mein Portal",
  },
  {
    role: "leg_admin",
    label: "LEG Admin",
    workspaceTitle: "LEG-Verwaltung",
  },
  {
    role: "partner_admin",
    label: "Gemeinde/EW",
    workspaceTitle: "Gemeinde/EW",
  },
  {
    role: "platform_admin",
    label: "Benutzerverwaltung",
    workspaceTitle: "Benutzerverwaltung",
  },
];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";
const accessTokenStorageKey = "sunterra.accessToken";
const devTokenStorageKey = "sunterra.devToken";
const developmentUiEnabled = () => import.meta.env.DEV;
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

function normalizedPortalPath(pathname: string) {
  return pathname === "/" ||
    pathname === "/registrieren" ||
    pathname === "/login" ||
    pathname === "/reset-password" ||
    pathname === "/app"
    ? pathname
    : "/";
}

function roleLabel(role: Role) {
  return demoRoles.find((demoRole) => demoRole.role === role)?.label ?? role;
}

function adminMfaRequired(user: CurrentUser) {
  return user.role !== "participant" && user.mfa_satisfied === false;
}

function membershipStatusLabel(status: string) {
  switch (status) {
    case "pending_email_verification":
      return "E-Mail-Verifikation offen";
    case "pending_required_documents":
      return "Pflichtdokumente offen";
    case "pending_eligibility_review":
      return "Teilnahmeberechtigung in Pruefung";
    case "eligibility_stopped":
      return "Teilnahmeberechtigung gestoppt";
    case "active":
      return "Mitgliedschaft aktiv";
    default:
      return status;
  }
}

function textToBase64(value: string) {
  const bytes = new TextEncoder().encode(value);
  const binary = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");

  return window.btoa(binary);
}

function mutationTypeLabel(mutationType: string) {
  return (
    regularMutationTypeOptions.find((option) => option.value === mutationType)
      ?.label ??
    specialMutationTypeOptions.find((option) => option.value === mutationType)
      ?.label ??
    mutationType
  );
}

function partnerStatusLabel(status: string) {
  const labels: Record<PartnerPackageStatus, string> = {
    created: "Erstellt",
    received: "Empfangen",
    in_review: "In Prüfung",
    processed: "Verarbeitet",
    question: "Rückfrage",
    technically_not_possible: "Technisch nicht möglich",
  };

  return status in labels ? labels[status as PartnerPackageStatus] : status;
}

function isSpecialMutationType(
  mutationType: string,
): mutationType is SpecialMutationType {
  return specialMutationTypeOptions.some((option) => option.value === mutationType);
}

function requestedRoleLabel(value: string | number | undefined) {
  return (
    roleOptions.find((option) => option.value === value)?.label ??
    String(value ?? "")
  );
}

function addressLine(address: ApiSchemas["AddressRead"] | null | undefined) {
  return address
    ? `${address.street}, ${address.postal_code} ${address.city}, ${address.country}`
    : "Keine Adresse";
}

function preferredContactChannelFromApi(value: string): PreferredContactChannel {
  return value === "phone" ? "phone" : "email";
}

function mutationDetailLines(
  mutationType: string,
  details: MutationDetails,
  newAddress: ApiSchemas["AddressRead"] | null | undefined,
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
  const showDevelopmentUi = developmentUiEnabled();
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });
  const [session, setSession] = useState<SessionState>({ kind: "anonymous" });
  const [routePath, setRoutePath] = useState(() =>
    normalizedPortalPath(window.location.pathname),
  );
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginTotpCode, setLoginTotpCode] = useState("");
  const [loginError, setLoginError] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteDisplayName, setInviteDisplayName] = useState("");
  const [participantInvitation, setParticipantInvitation] =
    useState<ParticipantInvitation | null>(null);
  const [onboardingToken, setOnboardingToken] = useState("");
  const [selfServiceEmail, setSelfServiceEmail] = useState("");
  const [selfServiceDisplayName, setSelfServiceDisplayName] = useState("");
  const [selfServiceMeteringPointId, setSelfServiceMeteringPointId] =
    useState("");
  const [selfServiceStreet, setSelfServiceStreet] = useState("");
  const [selfServicePostalCode, setSelfServicePostalCode] = useState("");
  const [selfServiceCity, setSelfServiceCity] = useState("");
  const [selfServiceOnboarding, setSelfServiceOnboarding] =
    useState<SelfServiceOnboardingResponse | null>(null);
  const [selfServiceInterest, setSelfServiceInterest] =
    useState<InterestRecord | null>(null);
  const [participantSetupDisplayName, setParticipantSetupDisplayName] =
    useState("");
  const [participantSetupPassword, setParticipantSetupPassword] = useState("");
  const [identityCheckpoint, setIdentityCheckpoint] =
    useState<IdentityCheckpoint | null>(null);
  const [emailVerification, setEmailVerification] =
    useState<EmailVerificationResponse | null>(null);
  const [participantMembership, setParticipantMembership] =
    useState<ParticipantMembership | null>(null);
  const [documentKey, setDocumentKey] = useState("portal_terms");
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentVersion, setDocumentVersion] = useState("");
  const [documentContent, setDocumentContent] = useState("");
  const [publishedDocumentVersion, setPublishedDocumentVersion] =
    useState<DocumentVersion | null>(null);
  const [currentDocuments, setCurrentDocuments] = useState<CurrentDocument[]>([]);
  const [consentCheckedByDocumentId, setConsentCheckedByDocumentId] = useState<
    Record<string, boolean>
  >({});
  const [consentSavedByDocumentId, setConsentSavedByDocumentId] = useState<
    Record<string, boolean>
  >({});
  const [consentHistory, setConsentHistory] = useState<ConsentEvidence[]>([]);
  const [contactChannels, setContactChannels] =
    useState<ParticipantContactChannels | null>(null);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [preferredContactChannel, setPreferredContactChannel] =
    useState<PreferredContactChannel>("email");
  const [contactChannelSaved, setContactChannelSaved] = useState(false);
  const [contactChannelError, setContactChannelError] = useState("");
  const [pilotFeedbackCategory, setPilotFeedbackCategory] = useState("process");
  const [pilotFeedbackContext, setPilotFeedbackContext] = useState("");
  const [pilotFeedbackMessage, setPilotFeedbackMessage] = useState("");
  const [submittedPilotFeedback, setSubmittedPilotFeedback] =
    useState<PilotFeedback | null>(null);
  const [pilotFeedbackError, setPilotFeedbackError] = useState("");
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
  const [adminPilotFeedback, setAdminPilotFeedback] = useState<PilotFeedback[]>(
    [],
  );
  const [adminPilotFeedbackNotes, setAdminPilotFeedbackNotes] = useState<
    Record<string, string>
  >({});
  const [adminPilotFeedbackError, setAdminPilotFeedbackError] = useState("");
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
  const [partnerTasks, setPartnerTasks] = useState<PartnerTask[]>([]);
  const [partnerTaskError, setPartnerTaskError] = useState("");
  const [userAccounts, setUserAccounts] = useState<UserAccount[]>([]);
  const [userManagementError, setUserManagementError] = useState("");
  const [createdUserAccount, setCreatedUserAccount] =
    useState<UserAccount | null>(null);
  const [updatedUserAccountId, setUpdatedUserAccountId] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserDisplayName, setNewUserDisplayName] = useState("");
  const [newUserRole, setNewUserRole] = useState<Role>("leg_admin");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [passwordResetUserId, setPasswordResetUserId] = useState("");
  const [passwordResetValue, setPasswordResetValue] = useState("");
  const [passwordResetResult, setPasswordResetResult] =
    useState<UserAccount | null>(null);
  const [publicPasswordResetEmail, setPublicPasswordResetEmail] = useState("");
  const [publicPasswordResetPassword, setPublicPasswordResetPassword] =
    useState("");
  const [publicPasswordResetStatus, setPublicPasswordResetStatus] =
    useState("");
  const [publicPasswordResetError, setPublicPasswordResetError] = useState("");
  const [partnerAdminEmail, setPartnerAdminEmail] = useState("");
  const [partnerAdminDisplayName, setPartnerAdminDisplayName] = useState("");
  const [partnerAdminOrganization, setPartnerAdminOrganization] = useState("");
  const [partnerAdminPassword, setPartnerAdminPassword] = useState("");
  const [createdPartnerAdmin, setCreatedPartnerAdmin] =
    useState<UserAccount | null>(null);
  const [partnerAdminError, setPartnerAdminError] = useState("");
  const [totpEnrollment, setTotpEnrollment] =
    useState<TotpEnrollmentResponse | null>(null);
  const [totpEnrollmentError, setTotpEnrollmentError] = useState("");

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

  useEffect(() => {
    function syncRoute() {
      setRoutePath(normalizedPortalPath(window.location.pathname));
    }

    window.addEventListener("popstate", syncRoute);

    return () => {
      window.removeEventListener("popstate", syncRoute);
    };
  }, []);

  useEffect(() => {
    const storedToken =
      window.localStorage.getItem(accessTokenStorageKey) ??
      window.localStorage.getItem(devTokenStorageKey);

    if (storedToken) {
      void loadCurrentUser(storedToken);
    }
  }, []);

  function navigate(path: string) {
    const normalizedPath = normalizedPortalPath(path);
    window.history.pushState({}, "", normalizedPath);
    setRoutePath(normalizedPath);
  }

  async function loadCurrentUser(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      window.localStorage.removeItem(accessTokenStorageKey);
      window.localStorage.removeItem(devTokenStorageKey);
      setSession({ kind: "anonymous" });
      setParticipantMembership(null);
      setCurrentDocuments([]);
      setConsentHistory([]);
      setConsentCheckedByDocumentId({});
      setConsentSavedByDocumentId({});
      return;
    }

    const user = (await response.json()) as CurrentUser;
    setSession({ kind: "authenticated", token, user });
    if (user.role === "participant") {
      void loadCurrentDocument(token);
      void loadConsentHistory(token);
      void loadContactChannels(token);
      void loadParticipantMembership(token);
    } else {
      setParticipantMembership(null);
      setCurrentDocuments([]);
      setConsentHistory([]);
      setConsentCheckedByDocumentId({});
      setConsentSavedByDocumentId({});
    }
    if (!adminMfaRequired(user) && user.role === "leg_admin") {
      void loadAdminMutationRequests(token);
      void loadAdminPilotFeedback(token);
    } else {
      setAdminMutationRequests([]);
      setAdminPilotFeedback([]);
      setAdminPilotFeedbackNotes({});
    }
    if (!adminMfaRequired(user) && user.role === "partner_admin") {
      void loadPartnerMutationPackages(token);
      void loadPartnerMemberRegister(token);
      void loadPartnerTasks(token);
    } else {
      setPartnerPackages([]);
      setPartnerPackageDetails({});
      setPartnerMemberRegister(null);
      setPartnerTasks([]);
    }
    if (!adminMfaRequired(user) && user.role === "platform_admin") {
      void loadUserAccounts(token);
    } else {
      setUserAccounts([]);
    }
    if (!adminMfaRequired(user)) {
      setTotpEnrollment(null);
      setTotpEnrollmentError("");
    }
  }

  function loginAs(role: Role) {
    const token = `dev:${role}`;
    window.localStorage.setItem(accessTokenStorageKey, token);
    window.localStorage.setItem(devTokenStorageKey, token);
    void loadCurrentUser(token);
    navigate("/app");
  }

  async function loginWithPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginError("");

    const loginRequest: LoginRequest = {
      email: loginEmail,
      password: loginPassword,
    };
    if (loginTotpCode.trim()) {
      loginRequest.totp_code = loginTotpCode.trim();
    }
    const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(loginRequest),
    });

    if (!response.ok) {
      setLoginError("Login fehlgeschlagen");
      return;
    }

    const auth = (await response.json()) as AuthTokenResponse;
    window.localStorage.setItem(accessTokenStorageKey, auth.access_token);
    window.localStorage.removeItem(devTokenStorageKey);
    setTotpEnrollment(null);
    setTotpEnrollmentError("");
    setSession({
      kind: "authenticated",
      token: auth.access_token,
      user: auth.user,
    });
    void loadCurrentUser(auth.access_token);
    navigate("/app");
  }

  function logout() {
    window.localStorage.removeItem(accessTokenStorageKey);
    window.localStorage.removeItem(devTokenStorageKey);
    setSession({ kind: "anonymous" });
    setParticipantMembership(null);
    setCurrentDocuments([]);
    setConsentHistory([]);
    setConsentCheckedByDocumentId({});
    setConsentSavedByDocumentId({});
    setTotpEnrollment(null);
    setTotpEnrollmentError("");
    navigate("/");
  }

  async function enrollTotpMfa() {
    if (session.kind !== "authenticated") {
      return;
    }

    setTotpEnrollmentError("");
    const response = await fetch(`${apiBaseUrl}/api/auth/mfa/totp/enroll`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
      },
    });

    if (response.ok) {
      const enrollment = (await response.json()) as TotpEnrollmentResponse;
      setTotpEnrollment(enrollment);
      return;
    }

    setTotpEnrollmentError("TOTP-MFA konnte nicht eingerichtet werden");
  }

  async function createParticipantInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const invitationCreate: ParticipantInvitationCreate = {
      email: inviteEmail,
      display_name: inviteDisplayName,
    };
    const response = await fetch(
      `${apiBaseUrl}/api/admin/participant-invitations`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(invitationCreate),
      },
    );

    if (response.ok) {
      const invitation = (await response.json()) as ParticipantInvitation;
      setParticipantInvitation(invitation);
    }
  }

  async function startSelfServiceOnboarding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const onboardingCreate: SelfServiceOnboardingCreate = {
      email: selfServiceEmail,
    };
    if (selfServiceDisplayName.trim()) {
      onboardingCreate.display_name = selfServiceDisplayName.trim();
    }
    if (selfServiceMeteringPointId.trim()) {
      onboardingCreate.metering_point_id = selfServiceMeteringPointId.trim();
    }
    if (selfServiceStreet.trim()) {
      onboardingCreate.street = selfServiceStreet.trim();
    }
    if (selfServicePostalCode.trim()) {
      onboardingCreate.postal_code = selfServicePostalCode.trim();
    }
    if (selfServiceCity.trim()) {
      onboardingCreate.city = selfServiceCity.trim();
    }
    const response = await fetch(
      `${apiBaseUrl}/api/auth/self-service-onboarding-requests`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(onboardingCreate),
      },
    );

    if (response.status === 202) {
      const interest = (await response.json()) as InterestRecord;
      setSelfServiceInterest(interest);
      setSelfServiceOnboarding(null);
      setIdentityCheckpoint(null);
      return;
    }

    if (response.ok) {
      const onboarding =
        (await response.json()) as SelfServiceOnboardingResponse;
      setSelfServiceInterest(null);
      setSelfServiceOnboarding(onboarding);
      setIdentityCheckpoint(onboarding.identity_checkpoint);
      setParticipantSetupDisplayName("");
      setParticipantSetupPassword("");
    }
  }

  async function verifySelfServiceEmail() {
    if (
      selfServiceOnboarding === null ||
      selfServiceOnboarding.dev_email_verification_token === null
    ) {
      return;
    }

    const verificationToken = selfServiceOnboarding.dev_email_verification_token;
    const verifyResponse = await fetch(
      (
        `${apiBaseUrl}/api/auth/email-verifications/` +
        `${verificationToken}/verify`
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

  }

  async function completeParticipantAccountSetup(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (selfServiceOnboarding === null) {
      return;
    }

    const accountSetup: ParticipantAccountSetup = {
      display_name: participantSetupDisplayName,
      password: participantSetupPassword,
    };
    const response = await fetch(
      `${apiBaseUrl}/api/auth/participant-account-setup`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${selfServiceOnboarding.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(accountSetup),
      },
    );

    if (!response.ok) {
      return;
    }

    const auth = (await response.json()) as AuthTokenResponse;
    window.localStorage.setItem(accessTokenStorageKey, auth.access_token);
    setSession({
      kind: "authenticated",
      token: auth.access_token,
      user: auth.user,
    });
    void loadCurrentUser(auth.access_token);
    navigate("/app");
  }

  async function publishDocumentVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const documentVersionCreate: DocumentVersionCreate = {
      document_key: documentKey,
      title: documentTitle,
      version: documentVersion,
      content: documentContent,
      context: "participant_onboarding",
    };
    const response = await fetch(`${apiBaseUrl}/api/admin/document-versions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(documentVersionCreate),
    });

    if (response.ok) {
      const published = (await response.json()) as DocumentVersion;
      setPublishedDocumentVersion(published);
    }
  }

  async function loadParticipantMembership(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/participants/me/membership`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const membership =
        (await response.json()) as Partial<ParticipantMembership>;
      if (membership.membership_status) {
        setParticipantMembership(membership as ParticipantMembership);
      }
    }
  }

  async function loadCurrentDocument(token: string) {
    const documents: CurrentDocument[] = [];
    for (const documentKey of REQUIRED_PARTICIPANT_DOCUMENT_KEYS) {
      const response = await fetch(
        `${apiBaseUrl}/api/documents/current?document_key=${documentKey}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (response.ok) {
        const document = (await response.json()) as Partial<CurrentDocument>;
        if (isCurrentDocument(document)) {
          documents.push(document);
        }
      }
    }
    setCurrentDocuments(documents);
  }

  async function loadConsentHistory(token: string) {
    const response = await fetch(`${apiBaseUrl}/api/participants/me/consent-evidence`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const history = (await response.json()) as unknown;
      setConsentHistory(Array.isArray(history) ? (history as ConsentEvidence[]) : []);
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
      setPreferredContactChannel(
        preferredContactChannelFromApi(channels.preferred_contact_channel),
      );
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

  async function loadAdminPilotFeedback(token: string) {
    setAdminPilotFeedbackError("");
    const response = await fetch(`${apiBaseUrl}/api/admin/pilot-feedback`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const records = (await response.json()) as PilotFeedback[];
      setAdminPilotFeedback(Array.isArray(records) ? records : []);
      return;
    }

    setAdminPilotFeedbackError("Pilotfeedback konnte nicht geladen werden");
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

  async function loadPartnerTasks(token: string) {
    setPartnerTaskError("");
    const response = await fetch(`${apiBaseUrl}/api/partner/tasks`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const tasks = (await response.json()) as PartnerTask[];
      setPartnerTasks(tasks);
      return;
    }

    setPartnerTaskError("Partner-Aufgaben konnten nicht geladen werden");
  }

  async function loadUserAccounts(token: string) {
    setUserManagementError("");
    const response = await fetch(`${apiBaseUrl}/api/admin/users`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const accounts = (await response.json()) as UserAccount[];
      setUserAccounts(Array.isArray(accounts) ? accounts : []);
      return;
    }

    setUserManagementError("Benutzerkonten konnten nicht geladen werden");
  }

  async function createPlatformUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setUserManagementError("");
    const userCreate: UserAccountCreate = {
      email: newUserEmail,
      display_name: newUserDisplayName,
      role: newUserRole,
      password: newUserPassword,
    };
    const response = await fetch(`${apiBaseUrl}/api/admin/users`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(userCreate),
    });

    if (response.ok) {
      const account = (await response.json()) as UserAccount;
      setCreatedUserAccount(account);
      setNewUserEmail("");
      setNewUserDisplayName("");
      setNewUserPassword("");
      await loadUserAccounts(session.token);
      return;
    }

    setUserManagementError("Benutzerkonto konnte nicht erstellt werden");
  }

  async function updateUserAccount(
    userId: string,
    update: ApiSchemas["UserAccountUpdate"],
  ): Promise<UserAccount | null> {
    if (session.kind !== "authenticated") {
      return null;
    }

    setUserManagementError("");
    const response = await fetch(`${apiBaseUrl}/api/admin/users/${userId}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(update),
    });

    if (response.ok) {
      const account = (await response.json()) as UserAccount;
      setUserAccounts((current) =>
        current.map((existing) => (existing.id === account.id ? account : existing)),
      );
      return account;
    }

    setUserManagementError("Benutzerkonto konnte nicht aktualisiert werden");
    return null;
  }

  async function updateUserAccountDetails(
    event: FormEvent<HTMLFormElement>,
    userId: string,
  ) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const updated = await updateUserAccount(userId, {
      display_name: String(formData.get("display_name") ?? "").trim(),
      role: formData.get("role") as Role,
    });

    if (updated !== null) {
      setUpdatedUserAccountId(updated.id);
    }
  }

  async function resetUserPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const passwordReset: UserPasswordReset = { password: passwordResetValue };
    const response = await fetch(
      `${apiBaseUrl}/api/admin/users/${passwordResetUserId}/reset-password`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(passwordReset),
      },
    );

    if (response.ok) {
      const account = (await response.json()) as UserAccount;
      setPasswordResetResult(account);
      setPasswordResetValue("");
      await loadUserAccounts(session.token);
    }
  }

  async function requestPublicPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPublicPasswordResetError("");
    setPublicPasswordResetStatus("");

    const resetRequest: PasswordResetRequestCreate = {
      email: publicPasswordResetEmail,
    };
    const response = await fetch(`${apiBaseUrl}/api/auth/password-reset/request`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(resetRequest),
    });

    if (!response.ok) {
      setPublicPasswordResetError("Reset-Link konnte nicht gesendet werden");
      return;
    }

    const status = (await response.json()) as PasswordResetStatus;
    if (status.status === "password_reset_requested") {
      setPublicPasswordResetStatus(
        "Wenn ein aktives Konto existiert, wurde ein Reset-Link gesendet.",
      );
    }
  }

  async function confirmPublicPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPublicPasswordResetError("");
    setPublicPasswordResetStatus("");

    const resetToken = new URLSearchParams(window.location.search).get("token") ?? "";
    const resetConfirm: PasswordResetConfirm = {
      token: resetToken,
      password: publicPasswordResetPassword,
    };
    const response = await fetch(`${apiBaseUrl}/api/auth/password-reset/confirm`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(resetConfirm),
    });

    if (!response.ok) {
      setPublicPasswordResetError("Passwort konnte nicht aktualisiert werden");
      return;
    }

    const status = (await response.json()) as PasswordResetStatus;
    if (status.status === "password_reset_completed") {
      setPublicPasswordResetPassword("");
      setPublicPasswordResetStatus("Passwort wurde aktualisiert");
    }
  }

  async function createPartnerAdminUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setPartnerAdminError("");
    const partnerAdminCreate: PartnerAdminUserCreate = {
      email: partnerAdminEmail,
      display_name: partnerAdminDisplayName,
      organization: partnerAdminOrganization,
      password: partnerAdminPassword,
    };
    const response = await fetch(`${apiBaseUrl}/api/admin/partner-admin-users`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(partnerAdminCreate),
    });

    if (response.ok) {
      const account = (await response.json()) as UserAccount;
      setCreatedPartnerAdmin(account);
      setPartnerAdminEmail("");
      setPartnerAdminDisplayName("");
      setPartnerAdminOrganization("");
      setPartnerAdminPassword("");
      return;
    }

    setPartnerAdminError("Gemeinde/EW-Zugang konnte nicht erstellt werden");
  }

  function contactChannelLabel(channel: string) {
    return channel === "phone" ? "Telefon" : "E-Mail";
  }

  async function saveContactChannels(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setContactChannelSaved(false);
    setContactChannelError("");
    const contactChannelsUpdate: ParticipantContactChannelsUpdate = {
      phone_number: phoneNumber.trim() || null,
      preferred_contact_channel: preferredContactChannel,
    };
    const response = await fetch(`${apiBaseUrl}/api/participants/me/contact-channels`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(contactChannelsUpdate),
    });

    if (response.ok) {
      const channels = (await response.json()) as ParticipantContactChannels;
      setContactChannels(channels);
      setPhoneNumber(channels.phone_number ?? "");
      setPreferredContactChannel(
        preferredContactChannelFromApi(channels.preferred_contact_channel),
      );
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

  async function submitPilotFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    setPilotFeedbackError("");
    setSubmittedPilotFeedback(null);
    const feedback: PilotFeedbackCreate = {
      category: pilotFeedbackCategory,
      message: pilotFeedbackMessage,
    };
    if (pilotFeedbackContext.trim()) {
      feedback.context = pilotFeedbackContext.trim();
    }
    const response = await fetch(`${apiBaseUrl}/api/pilot-feedback`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(feedback),
    });

    if (response.ok) {
      const submitted = (await response.json()) as PilotFeedback;
      setSubmittedPilotFeedback(submitted);
      setPilotFeedbackMessage("");
      return;
    }

    const error = (await response.json()) as { detail?: unknown };
    setPilotFeedbackError(
      typeof error.detail === "string"
        ? error.detail
        : "Pilotfeedback konnte nicht gespeichert werden",
    );
  }

  async function markPilotFeedbackRolloutRelevant(feedbackId: string) {
    if (session.kind !== "authenticated") {
      return;
    }

    setAdminPilotFeedbackError("");
    const update: PilotFeedbackUpdate = {
      status: "resolved",
      rollout_relevance: "blocks_public_rollout",
      admin_note: adminPilotFeedbackNotes[feedbackId]?.trim() || null,
    };
    const response = await fetch(
      `${apiBaseUrl}/api/admin/pilot-feedback/${feedbackId}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(update),
      },
    );

    if (response.ok) {
      const updated = (await response.json()) as PilotFeedback;
      setAdminPilotFeedback((current) =>
        current.map((feedback) =>
          feedback.id === updated.id ? updated : feedback,
        ),
      );
      setAdminPilotFeedbackNotes((current) => ({
        ...current,
        [feedbackId]: updated.admin_note ?? "",
      }));
      return;
    }

    const error = (await response.json()) as { detail?: unknown };
    setAdminPilotFeedbackError(
      typeof error.detail === "string"
        ? error.detail
        : "Pilotfeedback konnte nicht markiert werden",
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
    const reviewDecision: MutationReviewDecision =
      decision === "rejected"
        ? {
            decision,
            reason: reviewReasons[mutationRequestId] ?? "",
          }
        : { decision };
    const response = await fetch(
      `${apiBaseUrl}/api/admin/mutation-requests/${mutationRequestId}/review-decision`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(reviewDecision),
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
    const fileEvidenceCreate: FileEvidenceCreate = {
      document_type: "mutation_review_supporting_document",
      purpose: "mutation_review",
      version: draft.version,
      filename: draft.filename,
      content_type: draft.contentType,
      content_base64: textToBase64(draft.content),
    };
    const response = await fetch(
      `${apiBaseUrl}/api/admin/mutation-requests/${mutationRequestId}/file-evidence`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(fileEvidenceCreate),
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
    const packageCreate: MutationPackageCreate = {
      quarter: packageQuarter,
    };
    const response = await fetch(`${apiBaseUrl}/api/admin/mutation-packages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(packageCreate),
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
    const statusUpdate: MutationPackageStatusUpdate = {
      status: draft.status,
      ...(reference ? { reference } : {}),
    };
    const response = await fetch(
      `${apiBaseUrl}/api/partner/mutation-packages/${packageId}/status`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(statusUpdate),
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
      await loadPartnerTasks(session.token);
      return;
    }

    const error = (await response.json()) as { detail?: string };
    setPartnerPackageError(
      error.detail ?? "Paketstatus konnte nicht aktualisiert werden",
    );
  }

  async function submitConsentEvidence(
    event: FormEvent<HTMLFormElement>,
    currentDocument: CurrentDocument,
  ) {
    event.preventDefault();

    if (
      session.kind !== "authenticated" ||
      !consentCheckedByDocumentId[currentDocument.id]
    ) {
      return;
    }

    const consentEvidenceCreate: ConsentEvidenceCreate = {
      document_version_id: currentDocument.id,
      context: "participant_onboarding",
      accepted: true,
    };
    const response = await fetch(`${apiBaseUrl}/api/participants/me/consent-evidence`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(consentEvidenceCreate),
    });

    if (response.ok) {
      setConsentSavedByDocumentId((previous) => ({
        ...previous,
        [currentDocument.id]: true,
      }));
      await loadConsentHistory(session.token);
    }
  }

  async function submitMutation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (session.kind !== "authenticated") {
      return;
    }

    const mutationPayload: MutationRequestCreate = {
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
      window.localStorage.setItem(accessTokenStorageKey, acceptance.access_token);
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
      navigate("/app");
    }
  }

  const activeWorkspace =
    session.kind === "authenticated"
      ? demoRoles.find((demoRole) => demoRole.role === session.user.role)
      : undefined;
  const canSetupSelfServiceAccount =
    selfServiceOnboarding !== null &&
    emailVerification?.email_verified === true &&
    identityCheckpoint?.required_level === "account_setup" &&
    identityCheckpoint.current_level === "email_verified";
  const canUseDevEmailVerification =
    showDevelopmentUi &&
    selfServiceOnboarding?.dev_email_verification_token !== null &&
    selfServiceOnboarding?.dev_email_verification_token !== undefined;

  const documentVersionForm = (
    <form
      className="invitation-form document-version-form"
      onSubmit={publishDocumentVersion}
    >
      <h3>Dokumentverwaltung</h3>
      <label>
        Dokumenttyp
        <select
          value={documentKey}
          onChange={(event) => setDocumentKey(event.target.value)}
        >
          <option value="privacy_notice">Datenschutzhinweis</option>
          <option value="portal_terms">Portal-Nutzungsbedingungen</option>
          <option value="leg_contract">LEG-Vertrag</option>
        </select>
      </label>
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
          onChange={(event) => setDocumentVersion(event.target.value)}
          required
        />
      </label>
      <label>
        Inhalt
        <textarea
          value={documentContent}
          onChange={(event) => setDocumentContent(event.target.value)}
          required
        />
      </label>
      <button type="submit">Dokumentversion veroeffentlichen</button>
      {publishedDocumentVersion ? (
        <div className="invitation-result" role="status">
          <p>Dokumentversion veroeffentlicht</p>
          <p>{publishedDocumentVersion.version}</p>
          <p>{publishedDocumentVersion.document_hash}</p>
        </div>
      ) : null}
    </form>
  );

  const partnerAdminUserForm = (
    <form className="invitation-form" onSubmit={createPartnerAdminUser}>
      <h3>Gemeinde/EW Zugang erstellen</h3>
      <p>
        Warnung: Dieser Zugang erhaelt Zugriff auf Gemeinde/EW-Aufgaben,
        Mutationspakete und rollenbezogene Mitgliederdaten der LEG.
      </p>
      <label>
        Gemeinde/EW E-Mail
        <input
          type="email"
          value={partnerAdminEmail}
          onChange={(event) => setPartnerAdminEmail(event.target.value)}
          required
        />
      </label>
      <label>
        Gemeinde/EW Anzeigename
        <input
          type="text"
          value={partnerAdminDisplayName}
          onChange={(event) => setPartnerAdminDisplayName(event.target.value)}
          required
        />
      </label>
      <label>
        Organisation / Verantwortung
        <input
          type="text"
          value={partnerAdminOrganization}
          onChange={(event) => setPartnerAdminOrganization(event.target.value)}
          required
        />
      </label>
      <label>
        Startpasswort
        <input
          type="password"
          value={partnerAdminPassword}
          onChange={(event) => setPartnerAdminPassword(event.target.value)}
          required
        />
      </label>
      <button type="submit">Gemeinde/EW Zugang erstellen</button>
      {createdPartnerAdmin ? (
        <div className="invitation-result" role="status">
          <p>Gemeinde/EW Zugang erstellt</p>
          <p>{createdPartnerAdmin.email}</p>
        </div>
      ) : null}
      {partnerAdminError ? (
        <div className="mutation-error" role="alert">
          <p>{partnerAdminError}</p>
        </div>
      ) : null}
    </form>
  );

  const userManagementPanel = (
    <section className="user-management" aria-label="Benutzerverwaltung">
      <form className="invitation-form" onSubmit={createPlatformUser}>
        <h3>Internes Konto erstellen</h3>
        <label>
          E-Mail
          <input
            type="email"
            value={newUserEmail}
            onChange={(event) => setNewUserEmail(event.target.value)}
            required
          />
        </label>
        <label>
          Anzeigename
          <input
            type="text"
            value={newUserDisplayName}
            onChange={(event) => setNewUserDisplayName(event.target.value)}
            required
          />
        </label>
        <label>
          Rolle
          <select
            value={newUserRole}
            onChange={(event) => setNewUserRole(event.target.value as Role)}
          >
            <option value="leg_admin">LEG Admin</option>
            <option value="platform_admin">Plattform Admin</option>
          </select>
        </label>
        <label>
          Startpasswort
          <input
            type="password"
            value={newUserPassword}
            onChange={(event) => setNewUserPassword(event.target.value)}
            required
          />
        </label>
        <button type="submit">Benutzer erstellen</button>
        {createdUserAccount ? (
          <div className="invitation-result" role="status">
            <p>Benutzer erstellt</p>
            <p>{createdUserAccount.email}</p>
          </div>
        ) : null}
      </form>

      <div className="user-list">
        <h3>Konten</h3>
        {userAccounts.length > 0 ? (
          userAccounts.map((account) => (
            <article
              aria-label={`Konto ${account.email}`}
              className="user-row"
              key={account.id}
            >
              <div>
                <strong>{account.display_name}</strong>
                <p>{account.email}</p>
                <p>
                  {roleLabel(account.role)} /{" "}
                  {account.active ? "aktiv" : "deaktiviert"}
                </p>
                {account.organization ? <p>{account.organization}</p> : null}
              </div>
              <form
                className="invitation-form"
                onSubmit={(event) =>
                  void updateUserAccountDetails(event, account.id)
                }
              >
                <label>
                  Anzeigename
                  <input
                    name="display_name"
                    type="text"
                    defaultValue={account.display_name}
                    required
                  />
                </label>
                <label>
                  Rolle
                  <select name="role" defaultValue={account.role}>
                    <option value="leg_admin">LEG Admin</option>
                    <option value="platform_admin">Plattform Admin</option>
                  </select>
                </label>
                <button type="submit">Aenderungen speichern</button>
                {updatedUserAccountId === account.id ? (
                  <div className="invitation-result" role="status">
                    <p>Benutzer aktualisiert</p>
                  </div>
                ) : null}
              </form>
              <div className="role-actions">
                <button
                  type="button"
                  onClick={() =>
                    void updateUserAccount(account.id, {
                      active: !account.active,
                    })
                  }
                >
                  {account.active ? "Deaktivieren" : "Aktivieren"}
                </button>
                <button
                  type="button"
                  onClick={() => setPasswordResetUserId(account.id)}
                >
                  Passwort resetten
                </button>
              </div>
            </article>
          ))
        ) : (
          <p>Keine Konten geladen</p>
        )}
      </div>

      <form className="invitation-form" onSubmit={resetUserPassword}>
        <h3>Startpasswort setzen</h3>
        <label>
          Konto
          <select
            value={passwordResetUserId}
            onChange={(event) => setPasswordResetUserId(event.target.value)}
            required
          >
            <option value="">Konto waehlen</option>
            {userAccounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.display_name} ({account.email})
              </option>
            ))}
          </select>
        </label>
        <label>
          Neues Startpasswort
          <input
            type="password"
            value={passwordResetValue}
            onChange={(event) => setPasswordResetValue(event.target.value)}
            required
          />
        </label>
        <button type="submit">Passwort resetten</button>
        {passwordResetResult ? (
          <div className="invitation-result" role="status">
            <p>Passwort zurueckgesetzt</p>
            <p>{passwordResetResult.email}</p>
          </div>
        ) : null}
      </form>

      {userManagementError ? (
        <div className="mutation-error" role="alert">
          <p>{userManagementError}</p>
        </div>
      ) : null}
    </section>
  );

  const acceptedDocumentVersionIds = new Set(
    consentHistory.map((evidence) => evidence.document_version_id),
  );
  const documentConsentForm = currentDocuments.length > 0 ? (
    <section className="document-consent-list" aria-label="Pflichtdokumente">
      {currentDocuments.map((currentDocument) => {
        const consentChecked =
          consentCheckedByDocumentId[currentDocument.id] ?? false;
        const consentSaved =
          consentSavedByDocumentId[currentDocument.id] ||
          acceptedDocumentVersionIds.has(currentDocument.id);

        return (
          <form
            key={currentDocument.id}
            className="document-consent"
            onSubmit={(event) => submitConsentEvidence(event, currentDocument)}
          >
            <h3>{currentDocument.title}</h3>
            <p>Version {currentDocument.version}</p>
            <p>{currentDocument.content}</p>
            <p>{currentDocument.document_hash}</p>
            <label>
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(event) =>
                  setConsentCheckedByDocumentId((previous) => ({
                    ...previous,
                    [currentDocument.id]: event.target.checked,
                  }))
                }
              />
              Ich stimme dieser Dokumentversion zu
            </label>
            <button type="submit" disabled={!consentChecked || consentSaved}>
              Zustimmen
            </button>
            {consentSaved ? (
              <div className="invitation-result" role="status">
                <p>Einwilligung gespeichert</p>
              </div>
            ) : null}
          </form>
        );
      })}
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
    </section>
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

  const pilotFeedbackForm = (
    <section className="pilot-feedback" aria-label="Pilotfeedback-Formular">
      <form className="invitation-form" onSubmit={submitPilotFeedback}>
        <h3>Pilotfeedback</h3>
        <label>
          Feedback-Kategorie
          <input
            type="text"
            value={pilotFeedbackCategory}
            onChange={(event) => setPilotFeedbackCategory(event.target.value)}
            required
          />
        </label>
        <label>
          Feedback-Kontext
          <input
            type="text"
            value={pilotFeedbackContext}
            onChange={(event) => setPilotFeedbackContext(event.target.value)}
          />
        </label>
        <label>
          Pilotfeedback
          <textarea
            value={pilotFeedbackMessage}
            onChange={(event) => setPilotFeedbackMessage(event.target.value)}
            required
          />
        </label>
        <button type="submit">Pilotfeedback senden</button>
        {submittedPilotFeedback ? (
          <div className="invitation-result" role="status">
            <p>Pilotfeedback gespeichert</p>
            <p>{submittedPilotFeedback.category}</p>
          </div>
        ) : null}
        {pilotFeedbackError ? (
          <div className="mutation-error" role="alert">
            <p>{pilotFeedbackError}</p>
          </div>
        ) : null}
      </form>
    </section>
  );

  const adminPilotFeedbackPanel = (
    <section className="admin-mutation-inbox" aria-label="Pilotfeedback">
      <h3>Pilotfeedback</h3>
      {adminPilotFeedback.length > 0 ? (
        <div className="admin-mutation-list">
          {adminPilotFeedback.map((feedback) => (
            <article className="admin-mutation-item" key={feedback.id}>
              <p>{feedback.category}</p>
              <p>{feedback.message}</p>
              {feedback.context ? <p>{feedback.context}</p> : null}
              <p>{feedback.user_email}</p>
              <p>{feedback.status}</p>
              {feedback.rollout_relevance ? (
                <p>{feedback.rollout_relevance}</p>
              ) : null}
              {feedback.admin_note ? <p>{feedback.admin_note}</p> : null}
              <label>
                Bearbeitungsnotiz
                <input
                  type="text"
                  value={
                    adminPilotFeedbackNotes[feedback.id] ??
                    feedback.admin_note ??
                    ""
                  }
                  onChange={(event) =>
                    setAdminPilotFeedbackNotes((current) => ({
                      ...current,
                      [feedback.id]: event.target.value,
                    }))
                  }
                />
              </label>
              <button
                type="button"
                onClick={() => void markPilotFeedbackRolloutRelevant(feedback.id)}
              >
                Rolloutrelevant erledigen
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p>Kein Pilotfeedback offen</p>
      )}
      {adminPilotFeedbackError ? (
        <div className="mutation-error" role="alert">
          <p>{adminPilotFeedbackError}</p>
        </div>
      ) : null}
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

  const partnerTasksView = (
    <section className="partner-tasks" aria-label="Partner-Aufgaben">
      <h3>Partner-Aufgaben</h3>
      {partnerTasks.length > 0 ? (
        <div className="partner-task-list">
          {partnerTasks.map((task) => (
            <div className="partner-task-item" key={task.task_id}>
              <p>Paket {task.package_id}</p>
              <p>{partnerStatusLabel(task.status)}</p>
              <p>{task.quarter}</p>
              <p>Wirksam ab: {task.effective_date}</p>
              <p>{task.record_count} Mutation</p>
              {task.reference ? <p>{task.reference}</p> : null}
              {task.reason ? <p>{task.reason}</p> : null}
              <p>{task.created_at}</p>
            </div>
          ))}
        </div>
      ) : (
        <p>Keine Partner-Aufgaben</p>
      )}
      {partnerTaskError ? (
        <div className="mutation-error" role="alert">
          <p>{partnerTaskError}</p>
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

  const totpMfaEnrollmentPanel =
    session.kind === "authenticated" && adminMfaRequired(session.user) ? (
      <section className="invitation-form" aria-label="TOTP-MFA einrichten">
        <h3>TOTP-MFA einrichten</h3>
        <p>Admin-Zugriff wird nach aktivierter TOTP-MFA freigegeben.</p>
        <button type="button" onClick={enrollTotpMfa}>
          TOTP-MFA einrichten
        </button>
        {totpEnrollment ? (
          <div className="invitation-result" role="status">
            <p>Authenticator Secret</p>
            <code>{totpEnrollment.secret}</code>
            <p>{totpEnrollment.otpauth_url}</p>
          </div>
        ) : null}
        {totpEnrollmentError ? (
          <div className="mutation-error" role="alert">
            <p>{totpEnrollmentError}</p>
          </div>
        ) : null}
      </section>
    ) : null;

  const statusPanel = (
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
              : "Verbindung wird geprueft"}
        </p>
        {backend.kind === "connected" ? (
          <p className="status-detail">
            {backend.health.service} {backend.health.version}
          </p>
        ) : backend.kind === "offline" ? (
          <p className="status-detail">Die Portaloberflaeche ist geladen.</p>
        ) : null}
      </div>
    </section>
  );

  const publicPasswordResetToken =
    routePath === "/reset-password"
      ? new URLSearchParams(window.location.search).get("token") ?? ""
      : "";
  const resetPasswordScreen = (
    <main className="portal-shell portal-shell--auth">
      <nav className="portal-nav" aria-label="Portalbereiche">
        <button type="button" onClick={() => navigate("/")}>
          SunTerra LEG Portal
        </button>
        <button type="button" onClick={() => navigate("/login")}>
          Einloggen
        </button>
      </nav>
      <section className="auth-panel" aria-labelledby="reset-password-title">
        <p className="eyebrow">Kontozugang</p>
        <h1 id="reset-password-title">Passwort zuruecksetzen</h1>
        {publicPasswordResetToken ? (
          <form className="invitation-form" onSubmit={confirmPublicPasswordReset}>
            <p>Reset-Token erkannt</p>
            <label>
              Neues Passwort
              <input
                type="password"
                value={publicPasswordResetPassword}
                onChange={(event) =>
                  setPublicPasswordResetPassword(event.target.value)
                }
                required
              />
            </label>
            <button type="submit">Passwort aktualisieren</button>
          </form>
        ) : (
          <form className="invitation-form" onSubmit={requestPublicPasswordReset}>
            <label>
              E-Mail fuer Passwortreset
              <input
                type="email"
                value={publicPasswordResetEmail}
                onChange={(event) =>
                  setPublicPasswordResetEmail(event.target.value)
                }
                required
              />
            </label>
            <button type="submit">Reset-Link senden</button>
          </form>
        )}
        {publicPasswordResetStatus ? (
          <div className="invitation-result" role="status">
            <p>{publicPasswordResetStatus}</p>
          </div>
        ) : null}
        {publicPasswordResetError ? (
          <div className="mutation-error" role="alert">
            <p>{publicPasswordResetError}</p>
          </div>
        ) : null}
      </section>
      {statusPanel}
    </main>
  );

  const selfServiceTopologyFields = (
    <>
      <label>
        Messpunkt-ID
        <input
          type="text"
          value={selfServiceMeteringPointId}
          onChange={(event) => setSelfServiceMeteringPointId(event.target.value)}
        />
      </label>
      <label>
        Strasse
        <input
          type="text"
          value={selfServiceStreet}
          onChange={(event) => setSelfServiceStreet(event.target.value)}
        />
      </label>
      <label>
        PLZ
        <input
          type="text"
          value={selfServicePostalCode}
          onChange={(event) => setSelfServicePostalCode(event.target.value)}
        />
      </label>
      <label>
        Ort
        <input
          type="text"
          value={selfServiceCity}
          onChange={(event) => setSelfServiceCity(event.target.value)}
        />
      </label>
    </>
  );

  const loginScreen = (
    <main className="portal-shell portal-shell--auth">
      <nav className="portal-nav" aria-label="Portalbereiche">
        <button type="button" onClick={() => navigate("/")}>
          SunTerra LEG Portal
        </button>
        <button type="button" onClick={() => navigate("/registrieren")}>
          Teilnahme starten
        </button>
      </nav>
      <section className="auth-panel" aria-labelledby="login-title">
        <p className="eyebrow">Gemeinsamer Zugang</p>
        <h1 id="login-title">Einloggen</h1>
        <p className="subtitle">
          Ein Login fuer Teilnehmer, LEG-Verwaltung, Gemeinde/EW und
          Benutzerverwaltung.
        </p>
        <form className="invitation-form" onSubmit={loginWithPassword}>
          <label>
            E-Mail
            <input
              type="email"
              value={loginEmail}
              onChange={(event) => setLoginEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Passwort
            <input
              type="password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              required
            />
          </label>
          <label>
            TOTP-Code
            <input
              type="text"
              inputMode="numeric"
              value={loginTotpCode}
              onChange={(event) => setLoginTotpCode(event.target.value)}
            />
          </label>
          <button type="submit">Einloggen</button>
          {loginError ? (
            <div className="mutation-error" role="alert">
              <p>{loginError}</p>
            </div>
          ) : null}
        </form>
        <button type="button" onClick={() => navigate("/reset-password")}>
          Passwort vergessen?
        </button>
        {showDevelopmentUi ? (
          <section className="dev-login-panel" aria-label="Lokale Demo-Rollen">
            <h2>Anmeldung erforderlich</h2>
            <p>
              Fuer die lokale Entwicklung kann eine Demo-Rolle genutzt werden.
            </p>
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
          </section>
        ) : null}
      </section>
      {statusPanel}
    </main>
  );

  if (routePath === "/registrieren") {
    return (
      <main className="portal-shell portal-shell--auth">
        <nav className="portal-nav" aria-label="Portalbereiche">
          <button type="button" onClick={() => navigate("/")}>
            SunTerra LEG Portal
          </button>
          <button type="button" onClick={() => navigate("/login")}>
            Einloggen
          </button>
        </nav>
        <section className="auth-panel" aria-labelledby="register-title">
          <p className="eyebrow">Teilnahme</p>
          <h1 id="register-title">Teilnahme starten</h1>
          <p className="subtitle">
            Starten Sie mit Ihrer E-Mail. Nach der Verifikation richten Sie Ihr
            Konto mit Name und Passwort ein.
          </p>
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
              />
            </label>
            {selfServiceTopologyFields}
            <button type="submit">Self-Service starten</button>
          </form>
          {selfServiceInterest ? (
            <section
              className="identity-checkpoint"
              aria-label="Interessensmeldung"
            >
              <h3>Interessensmeldung gespeichert</h3>
              <p>{selfServiceInterest.email}</p>
              <p>{selfServiceInterest.display_name}</p>
            </section>
          ) : null}
          {selfServiceOnboarding && identityCheckpoint ? (
            <section
              className="identity-checkpoint"
              aria-label="Identitaetspruefung"
            >
              <h3>Identitaetspruefung</h3>
              <p>Erforderlich: {identityCheckpoint.required_level}</p>
              <p>Aktuell: {identityCheckpoint.current_level}</p>
              <p>
                {identityCheckpoint.satisfied
                  ? "Checkpoint erfuellt"
                  : "Checkpoint offen"}
              </p>
              {canUseDevEmailVerification ? (
                <>
                  <p>{selfServiceOnboarding.dev_email_verification_token}</p>
                  <button
                    type="button"
                    disabled={identityCheckpoint.satisfied}
                    onClick={() => void verifySelfServiceEmail()}
                  >
                    Dev E-Mail verifizieren
                  </button>
                </>
              ) : null}
            </section>
          ) : null}
          {canSetupSelfServiceAccount ? (
            <form
              className="invitation-form"
              onSubmit={completeParticipantAccountSetup}
            >
              <h2>Konto einrichten</h2>
              <label>
                Anzeigename
                <input
                  type="text"
                  value={participantSetupDisplayName}
                  onChange={(event) =>
                    setParticipantSetupDisplayName(event.target.value)
                  }
                  required
                />
              </label>
              <label>
                Passwort
                <input
                  type="password"
                  value={participantSetupPassword}
                  onChange={(event) =>
                    setParticipantSetupPassword(event.target.value)
                  }
                  required
                />
              </label>
              <button type="submit">Konto einrichten</button>
            </form>
          ) : null}
        </section>
        {statusPanel}
      </main>
    );
  }

  if (routePath === "/login") {
    return loginScreen;
  }

  if (routePath === "/reset-password") {
    return resetPasswordScreen;
  }

  if (routePath === "/app") {
    if (session.kind !== "authenticated") {
      return loginScreen;
    }

    return (
      <main className="portal-shell portal-shell--workspace">
        <nav className="portal-nav" aria-label="Portalbereiche">
          <button type="button" onClick={() => navigate("/")}>
            SunTerra LEG Portal
          </button>
          <button type="button" onClick={logout}>
            Abmelden
          </button>
        </nav>
        {statusPanel}
        <section
          className="workspace-panel"
          aria-label="Geschuetzter Arbeitsbereich"
        >
          {participantMembership ? (
            <div className="membership-workspace">
              <h2>Mein Portal</h2>
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
                  <dd>
                    {membershipStatusLabel(
                      participantMembership.membership_status,
                    )}
                  </dd>
                </div>
              </dl>
              {participantMembership.eligibility_review_reason ? (
                <p>{participantMembership.eligibility_review_reason}</p>
              ) : null}
              <p className="billing-notice">
                {participantMembership.billing_notice}
              </p>
              {documentConsentForm}
              {contactChannelForm}
              {pilotFeedbackForm}
              {addressMutationForm}
            </div>
          ) : activeWorkspace ? (
            <div className="role-workspace">
              <header className="workspace-header">
                <div>
                  <p className="eyebrow">{roleLabel(session.user.role)}</p>
                  <h2>{activeWorkspace.workspaceTitle}</h2>
                  <p>{session.user.display_name}</p>
                </div>
              </header>
              {adminMfaRequired(session.user) ? (
                totpMfaEnrollmentPanel
              ) : (
                <>
                  {session.user.role === "leg_admin" ? (
                    <>
                      <form
                        className="invitation-form"
                        onSubmit={createParticipantInvitation}
                      >
                        <h3>Teilnehmer einladen</h3>
                        <label>
                          E-Mail
                          <input
                            type="email"
                            value={inviteEmail}
                            onChange={(event) =>
                              setInviteEmail(event.target.value)
                            }
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
                      {partnerAdminUserForm}
                      {documentVersionForm}
                      {adminPilotFeedbackPanel}
                      {adminMutationInbox}
                      {adminMutationPackages}
                    </>
                  ) : null}
                  {session.user.role === "partner_admin" ? (
                    <>
                      {partnerTasksView}
                      {partnerMemberRegisterView}
                      {partnerPackageInbox}
                    </>
                  ) : null}
                  {session.user.role === "platform_admin" ? userManagementPanel : null}
                  {session.user.role === "participant" ? (
                    <>
                      {documentConsentForm}
                      {contactChannelForm}
                      {pilotFeedbackForm}
                      {addressMutationForm}
                    </>
                  ) : null}
                </>
              )}
            </div>
          ) : null}
        </section>
      </main>
    );
  }

  if (routePath === "/") {
    return (
      <main className="portal-shell portal-shell--public">
        <nav className="portal-nav" aria-label="Portalbereiche">
          <button type="button" onClick={() => navigate("/")}>
            SunTerra LEG Portal
          </button>
          <button type="button" onClick={() => navigate("/login")}>
            Einloggen
          </button>
        </nav>
        <section className="hero-band" aria-labelledby="portal-title">
          <p className="eyebrow">SunTerra LEG Basadingen</p>
          <h1 id="portal-title">SunTerra LEG Portal</h1>
          <p className="subtitle">
            Das Portal fuer lokale Energie, transparente Teilnahme und die
            operative LEG-Verwaltung.
          </p>
          <div className="hero-actions">
            <button type="button" onClick={() => navigate("/registrieren")}>
              Teilnahme starten
            </button>
            <button type="button" onClick={() => navigate("/login")}>
              Einloggen
            </button>
          </div>
        </section>
        <section className="public-overview" aria-label="Portaluebersicht">
          <article>
            <h2>Was ist eine LEG?</h2>
            <p>
              Eine lokale Elektrizitaetsgemeinschaft verbindet Verbrauch,
              Produktion und Verwaltung in einem gemeinsamen digitalen Ablauf.
            </p>
          </article>
          <article>
            <h2>Wie funktioniert die Teilnahme?</h2>
            <p>
              Interessierte starten mit ihrer E-Mail, verifizieren den Zugang
              und fuehren die weiteren Schritte im geschuetzten Portal fort.
            </p>
          </article>
          <article>
            <h2>Arbeitsbereiche</h2>
            <p>
              Mein Portal, LEG-Verwaltung, Gemeinde/EW und Benutzerverwaltung
              fuehren direkt zu den relevanten Funktionen.
            </p>
          </article>
        </section>
        {statusPanel}
      </main>
    );
  }

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
            {pilotFeedbackForm}
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
                {partnerTasksView}
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
                {pilotFeedbackForm}
                {addressMutationForm}
              </>
            ) : null}
          </div>
        ) : (
          <>
            {showDevelopmentUi ? (
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
              </>
            ) : (
              <div>
                <h2>Anmeldung erforderlich</h2>
              </div>
            )}
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
              {selfServiceTopologyFields}
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
                {canUseDevEmailVerification ? (
                  <>
                    <p>{selfServiceOnboarding.dev_email_verification_token}</p>
                    <button
                      type="button"
                      disabled={identityCheckpoint.satisfied}
                      onClick={() => void verifySelfServiceEmail()}
                    >
                      Dev E-Mail verifizieren
                    </button>
                  </>
                ) : null}
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
