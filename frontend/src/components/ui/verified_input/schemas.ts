import { z } from "zod";

export const verifyFormSchema = z
  .object({
    email: z.string().email({ message: "Please enter a valid email address" }),
    countryCode: z.string().min(1, { message: "Country code is required" }),
    dialCode: z.string().min(1, { message: "Dial code is required" }),
    phone: z
      .string()
      .regex(/^\d+$/, { message: "Phone must contain only digits" })
      .min(7)
      .max(15),

    emailVerified: z.boolean(),
    phoneVerified: z.boolean(),
  })
  .refine((data) => data.emailVerified === true, {
    message: "Email must be verified",
    path: ["emailVerified"],
  })
  .refine((data) => data.phoneVerified === true, {
    message: "Phone must be verified",
    path: ["phoneVerified"],
  });

export type VerifyFormValues = z.infer<typeof verifyFormSchema>;
