import { publicConfig } from "@lib/config/public";
import { FetchHttpClient, HttpClient } from "@lib/FetchHttpClient";

const baseURL = publicConfig.apiUrl;
export const httpClient: HttpClient = new FetchHttpClient(baseURL);

export const microsoftClarityProjectId = publicConfig.microsoftClarityProjectId;
// export const authRequiredPathParamKey = "auth-required";
// export const authRequiredTypePathParamKey = "auth-type";
