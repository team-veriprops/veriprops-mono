import { z } from "zod";
import { TransactionCurrency } from "@/types/models";
import { MIN_PASSWORD_LENGTH } from "@components/website/auth/libs/auth/password-strength";

const passwordSchema = z
  .string()
  .min(MIN_PASSWORD_LENGTH, { message: `At least ${MIN_PASSWORD_LENGTH} characters` })
  .refine((p) => /[A-Z]/.test(p), { message: "Add an uppercase letter" })
  .refine((p) => /[a-z]/.test(p), { message: "Add a lowercase letter" })
  .refine((p) => /\d/.test(p), { message: "Add a number" });

const personSchema = z.object({
  firstName: z.string().min(1, "First name is required").max(60),
  lastName: z.string().min(1, "Last name is required").max(60),
});

const phoneFields = z.object({
  countryCode: z.string().min(2, "Select a country"),
  dialCode: z.string().min(1, "Select a dial code"),
  phone: z
    .string()
    .regex(/^\d+$/, "Phone must contain only digits")
    .min(7, "Phone is too short")
    .max(15, "Phone is too long"),
});

// ─── Signup ─────────────────────────────────────────────────────
export const signupStep1Schema = personSchema.extend({
  email: z.string().email("Enter a valid email"),
  password: passwordSchema,
});

export const signupStep2Schema = phoneFields.extend({
  emailVerified: z.literal(true, { message: "Verify your email" }),
  phoneVerified: z.literal(true, { message: "Verify your phone" }),
});

export const signupStep3Schema = z.object({
  countryOfResidence: z.string().min(2, "Select your country of residence"),
  timezone: z.string().min(1, "Select your timezone"),
  preferredCurrency: z.nativeEnum(TransactionCurrency),
});

export const signupStep4Schema = z.object({
  acceptedPlatformTerms: z.literal(true, { message: "Required to continue" }),
  acceptedPrivacyPolicy: z.literal(true, { message: "Required to continue" }),
});

export const signupSchema = signupStep1Schema
  .merge(signupStep2Schema)
  .merge(signupStep3Schema)
  .merge(signupStep4Schema);

export type SignupValues = z.infer<typeof signupSchema>;
export type SignupStep1Values = z.infer<typeof signupStep1Schema>;
export type SignupStep2Values = z.infer<typeof signupStep2Schema>;
export type SignupStep3Values = z.infer<typeof signupStep3Schema>;
export type SignupStep4Values = z.infer<typeof signupStep4Schema>;

// ─── Login ──────────────────────────────────────────────────────
export const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
  rememberMe: z.boolean().optional(),
});

export type LoginValues = z.infer<typeof loginSchema>;

// ─── Forgot / reset password ─────────────────────────────────────
export const forgotPasswordSchema = z.object({
  email: z.string().email("Enter a valid email"),
});

export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({
    password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });

export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

// ─── Profile completion (OAuth users) ────────────────────────────
export const profileCompletionSchema = phoneFields
  .merge(signupStep3Schema)
  .extend({
    phoneVerified: z.literal(true, { message: "Verify your phone" }),
  });

export type ProfileCompletionValues = z.infer<typeof profileCompletionSchema>;

// ─── Helpers ─────────────────────────────────────────────────────
export const RATE_LIMIT_WARN_AT = 5;
export const RATE_LIMIT_LOCKOUT_AT = 7;
export const RATE_LIMIT_LOCKOUT_MINUTES = 15;
