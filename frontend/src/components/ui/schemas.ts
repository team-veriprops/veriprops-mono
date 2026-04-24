import { z } from "zod";

export const addressSchema = z
  .object({
    address: z.string().min(5, "Select a valid address"),
    country: z.string().min(1),
    state: z.string().min(2, "State is required"),
    lga: z.string().optional(),
    city: z.string().optional(),
    area: z.string().optional(),
    street: z.string().optional(),
    streetNumber: z.string().optional(),
    postalCode: z.string().optional(),
    latitude: z.string().min(1, "Latitude missing"),
    longitude: z.string().min(1, "Longitude missing"),
    placeId: z.string().min(1, "Select an address from suggestions"),
  })
  .refine((data) => data.country === "Nigeria", {
    path: ["country"],
    message: "Address must be in Nigeria",
  });

export type AddressFormValues = z.infer<typeof addressSchema>;
