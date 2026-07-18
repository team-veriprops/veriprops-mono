import { publicConfig } from "@lib/config/public";
import { FetchHttpClient, HttpClient } from "@lib/FetchHttpClient";

const baseURL = publicConfig.apiUrl;

/** Concrete client — exposed only for session plumbing (proactive refresh). */
export const fetchHttpClient = new FetchHttpClient(baseURL);

/** The app-wide HTTP client every service consumes. */
export const httpClient: HttpClient = fetchHttpClient;

export const microsoftClarityProjectId = publicConfig.microsoftClarityProjectId;
