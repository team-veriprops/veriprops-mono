import { VerifiedInputType } from "@components/ui/verified_input/VerifiedInput";

export interface VerifiedInputVerificationProps {
  type: VerifiedInputType;
  otp?: string;
  onSuccess: () => void;
  onError: (errorMessage: string) => void;
}
