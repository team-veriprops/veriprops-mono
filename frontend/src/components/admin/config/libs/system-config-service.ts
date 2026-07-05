import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { ConfigKey, SystemConfigItem } from "@/types/systemConfig";

/**
 * System configuration API (PRD §14/§18.5, D28). Mirrors app/domain/system_config —
 * RBAC-gated admin settings. Backend owns defaults + coercion.
 */
export class SystemConfigService {
  constructor(private readonly http: HttpClient) {}

  list(): Promise<SuccessResponse<SystemConfigItem[]>> {
    return this.http.get(`/admin/config/settings`);
  }

  set(key: ConfigKey, value: number | string | boolean): Promise<SuccessResponse<SystemConfigItem[]>> {
    return this.http.put(`/admin/config/settings/${key}`, { value });
  }
}
