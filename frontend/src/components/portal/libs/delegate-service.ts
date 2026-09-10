import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import {
  AuthorizeCaseDelegate,
  CaseDelegate,
  CaseDelegateChallenge,
} from "@/types/delegate";

/**
 * Per-case delegate API (PRD §26.4.5). Mirrors the backend controller at
 * `app/domain/verification/delegate`.
 *
 * Every call is scoped by the verification in the path, and the backend proves the caller
 * owns that case before doing anything — so there is no customer id to send and none is
 * accepted. Confirmation carries only the code: which number is being confirmed comes
 * from the authorization already on the case, never from the browser.
 */
export class DelegateService {
  constructor(private readonly http: HttpClient) {}

  /** This case's delegate — a list of at most one. */
  list(verificationId: string): Promise<SuccessResponse<CaseDelegate[]>> {
    return this.http.get(`/verifications/${verificationId}/delegates`);
  }

  /** Nominate a delegate and send a code to their number. Nothing is visible yet. */
  authorize(
    verificationId: string,
    delegate: AuthorizeCaseDelegate,
  ): Promise<SuccessResponse<CaseDelegateChallenge>> {
    return this.http.post(`/verifications/${verificationId}/delegates`, delegate);
  }

  /** Confirm the code the delegate received. Their visibility begins here. */
  confirm(
    verificationId: string,
    code: string,
  ): Promise<SuccessResponse<CaseDelegate>> {
    return this.http.post(`/verifications/${verificationId}/delegates/confirm`, { code });
  }

  /** End the delegation. Effective on the next event. */
  revoke(verificationId: string): Promise<SuccessResponse<{ revoked: boolean }>> {
    return this.http.post(`/verifications/${verificationId}/delegates/revoke`);
  }
}
