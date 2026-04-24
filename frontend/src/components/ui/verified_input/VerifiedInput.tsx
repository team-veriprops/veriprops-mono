import { useState } from "react";
import { Input } from "@components/3rdparty/ui/input";
import { Button } from "@components/3rdparty/ui/button";
import { Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import VerificationModal from "./VerificationModal";
import type { UseFormReturn } from "react-hook-form";

import PhoneInputWithCountry from "../form/PhoneInputWithCountry";
import { toast } from "sonner";
import { VerifiedInputVerificationProps } from "@components/website/auth/signup/VerifyEmailPhoneForm";
import { verifyFormSchema, type VerifyFormValues } from "./schemas";

export { verifyFormSchema, type VerifyFormValues };

export enum VerifiedInputType {
  EMAIL = "Email",
  PHONE = "Phone"
}

interface VerifiedInputProps {
  form: UseFormReturn<VerifyFormValues>;
  field: "email" | "phone";
  label: string;
  type: VerifiedInputType;
  placeholder: string;
  inputType?: string;
  
  onSendVerificationMessage: (props: VerifiedInputVerificationProps) => void
  onValidateVerificationOtp: (props: VerifiedInputVerificationProps) => void
}

const VerifiedInput = ({ form, field, label, type, placeholder, inputType = "text", onSendVerificationMessage, onValidateVerificationOtp }: VerifiedInputProps) => {
  const [modalOpen, setModalOpen] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const verifiedField = `${field}Verified` as "emailVerified" | "phoneVerified";
  const isVerified = form.watch(verifiedField);
  const fieldError = form.formState.errors[field];
  const fieldValue = form.watch(field);

  const canVerify = !isVerified && fieldValue && !fieldError;
  const [otpError, setOtpError] = useState<string | null>(null);
  const handleVerifyClick = () => {
    setIsVerifying(true)

    onSendVerificationMessage({
      type: type,
      onSuccess: () => {
        setOtpError(null);
        toast("Verification code resent", { description: `A new code has been sent to your ${type.toLowerCase()}.` });
        setIsVerifying(false)
        setModalOpen(true);
      },
      onError: (errorMessage: string) => {
        setIsVerifying(false)
        setOtpError(errorMessage)
      }
    })
  };

  const handleVerified = () => {
    form.setValue(verifiedField, true, { shouldValidate: true });
    setOtpError(null);
    setIsVerifying(false)
    setModalOpen(false);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <div className="flex gap-2">
        {field === "phone" ? (
          <div className="flex-1">
            <PhoneInputWithCountry
              form={form}
              placeholder={placeholder}
              isVerified={isVerified}
              onChanged={() => {
                setOtpError(null);
                if (isVerified) {
                  form.setValue(verifiedField, false, { shouldValidate: true });
                }
              }}
            />
          </div>
        ) : (
          <div className="flex-1">
            <Input
              type={inputType}
              placeholder={placeholder}
              disabled={isVerified}
              {...form.register(field, {
                onChange: () => {
                  setOtpError(null);
                  if (isVerified) {
                    form.setValue(verifiedField, false, { shouldValidate: true });
                  }
                },
              })}
              className={isVerified ? "border-[hsl(var(--success))] focus-visible:ring-[hsl(var(--success))]" : ""}
            />
          </div>
        )}
        <AnimatePresence mode="wait">
          {isVerified ? (
            <motion.div
              key="verified"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
            >
              <Button variant="outline" disabled className="gap-1.5 border-[hsl(var(--success))] text-[hsl(var(--success))]">
                <Check className="w-4 h-4" /> Verified
              </Button>
            </motion.div>
          ) : (
            <motion.div
              key="verify"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
            >
              <Button
                type="button"
                variant={canVerify ? "default" : "outline"}
                disabled={!canVerify}
                onClick={handleVerifyClick}
              >
                  {isVerifying ? (
                    <span
                      className="inline-flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                      Sending code…
                    </span>
                  ) : (
                    <span>
                      Verify
                    </span>
                  )}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      {fieldError && <p className="text-sm text-destructive">{fieldError.message}</p>}

      {otpError && !fieldError && (
        <p className="text-sm text-destructive">
          {otpError}
        </p>
      )}

      <VerificationModal 
        open={modalOpen} 
        onClose={() => setModalOpen(false)} 
        onVerified={handleVerified} 
        type={type}
        
        onSendVerificationMessage={onSendVerificationMessage}
        onValidateVerificationOtp={onValidateVerificationOtp}
       />
    </div>
  );
};

export default VerifiedInput;