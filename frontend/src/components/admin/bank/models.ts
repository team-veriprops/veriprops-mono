/* eslint-disable @typescript-eslint/no-empty-object-type */

import { BaseQueryDto, PageRequest } from "@/types/models";

// Base Interfaces
export interface BankBaseDto {
  name: string
  shortName: string
  code: string
  countryCode: string
}

// Create DTO
export interface CreateBankDto extends BankBaseDto {
  
}

// Update DTO (full override)
export interface UpdateBankDto extends BankBaseDto {}

export interface SearchBankDto extends PageRequest, BaseQueryDto {
  status?: string;
  name?: string
  shortName?: string
  code?: string
  countryCode?: string
}

// Query DTO (combination of Create + PartialUpdate + BaseQuery)
export interface QueryBankDto extends CreateBankDto, BaseQueryDto {
  status: string;
}


