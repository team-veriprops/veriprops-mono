import { useState, useEffect, useRef, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { VerifiedInputType } from "./VerifiedInput";
import { VerifiedInputVerificationProps } from "@components/website/auth/signup/VerifyEmailPhoneForm";
import { XIcon } from "lucide-react";

interface VerificationModalProps {
  open: boolean;
  onClose: () => void;
  onVerified: () => void;
  type: VerifiedInputType;
  
  onSendVerificationMessage: (props: VerifiedInputVerificationProps) => void
  onValidateVerificationOtp: (props: VerifiedInputVerificationProps) => void
}

const OTP_LENGTH = 6;

const VerificationModal = ({ open, onClose, onVerified, type, onSendVerificationMessage, onValidateVerificationOtp }: VerificationModalProps) => {
  const [otp, setOtp] = useState<string[]>(Array(OTP_LENGTH).fill(""));
  const [countdown, setCountdown] = useState(30);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const inputsRef = useRef<(HTMLInputElement | null)[]>([]);

  const resetState = useCallback(() => {
    setOtp(Array(OTP_LENGTH).fill(""));
    setCountdown(30);
    setVerifying(false);
    setOtpError(null);
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => resetState(), 0)
      setTimeout(() => inputsRef.current[0]?.focus(), 100);
    }
  }, [open, resetState]);

  useEffect(() => {
    if (!open || countdown <= 0) return;
    const t = setInterval(() => setCountdown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, [open, countdown]);

  const handleChange = (index: number, value: string) => {
    if (!/^\d?$/.test(value)) return;
    const next = [...otp];
    next[index] = value;
    setOtp(next);
    setOtpError(null);
    if (value && index < OTP_LENGTH - 1) {
      inputsRef.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, OTP_LENGTH);
    const next = [...otp];
    text.split("").forEach((ch, i) => (next[i] = ch));
    setOtp(next);
    inputsRef.current[Math.min(text.length, OTP_LENGTH - 1)]?.focus();
  };

  const code = otp.join("");
  const isComplete = code.length === OTP_LENGTH;

  const handleConfirm = () => {
    setOtpError(null);
    setVerifying(true);

    onValidateVerificationOtp({
      type: type,
      otp: code,
      onSuccess: () => {
        setVerifying(false);
        toast.success(`${type} verified successfully!`);
        inputsRef.current[0]?.focus();
        onVerified();
      },
      onError: (errorMessage) => {
        setVerifying(false);
        setOtpError(errorMessage)
        setOtp(Array(OTP_LENGTH).fill(""));
        inputsRef.current[0]?.focus();
      }
    })
  };

  const handleResend = async() => {
    setResending(true);

    onSendVerificationMessage({
      type: type,
      onSuccess: () => {
        setOtpError(null)
        setResending(false);
        setCountdown(30);
        setOtp(Array(OTP_LENGTH).fill(""));
        inputsRef.current[0]?.focus();
        toast("Verification code resent", { description: `A new code has been sent to your ${type.toLowerCase()}.` });
      },
      onError: (errorMessage) => {
        setCountdown(30);
        setOtpError(errorMessage)
        setResending(false);
        setOtp(Array(OTP_LENGTH).fill(""));
        inputsRef.current[0]?.focus();
      }
    })
  };

  return (
    <Dialog open={open} onOpenChange={(newOpen) => {
      // Only allow closing programmatically
      if (!newOpen) return; // ignore backdrop clicks
      }}
    >
      <DialogContent showCloseButton={false} className="sm:max-w-md">
        <DialogHeader className="relative">
          <DialogTitle className="text-xl font-semibold">Verify {type}</DialogTitle>
          <button
            type="button"
            className="absolute -top-2 right-2 p-1 text-muted-foreground opacity-70 transition-opacity hover:opacity-100"
            onClick={onClose}
            aria-label="Close"
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </button>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Enter the 6-digit code sent to your {type.toLowerCase()}.
        </p>

        <div className="flex justify-center gap-2 my-4" onPaste={handlePaste}>
          {otp.map((digit, i) => (
            <motion.input
              key={i}
              ref={(el) => { inputsRef.current[i] = el; }}
              type="text"
              inputMode="numeric"
              maxLength={1}
              value={digit}
              onChange={(e) => handleChange(i, e.target.value)}
              onKeyDown={(e) => handleKeyDown(i, e)}
              className={`w-11 h-13 text-center text-lg font-semibold rounded-md border bg-background focus:outline-none focus:ring-2 transition-all ${otpError ? "border-destructive focus:ring-destructive" : "border-input focus:ring-ring"}`}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: i * 0.05 }}
            />
          ))}
        </div>

         <AnimatePresence>
          {otpError && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="text-sm text-destructive text-center"
            >
              {otpError}
            </motion.p>
          )}
        </AnimatePresence>

        <div className="text-center text-sm text-muted-foreground min-h-8 flex items-center justify-center">
          <AnimatePresence mode="wait">
            {countdown > 0 ? (
              <motion.span
                key="countdown"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                Resend in {countdown}s
              </motion.span>
            ) : (
              <motion.div
                key="resend"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                whileHover={{ scale: resending ? 1 : 1.05 }}
                whileTap={{ scale: resending ? 1 : 0.95 }}
              >
                <Button variant="link" size="sm" onClick={handleResend} disabled={resending} className="text-primary p-0 h-auto">
                  <AnimatePresence mode="wait">
                    {resending ? (
                      <motion.span key="resending" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="inline-flex items-center gap-1.5">
                        <span className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                        Resending…
                      </motion.span>
                    ) : (
                      <motion.span key="resend-text" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        Resend Code
                      </motion.span>
                    )}
                  </AnimatePresence>
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex gap-3 mt-2">
          <Button variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button className="flex-1" disabled={!isComplete || verifying} onClick={handleConfirm}>
            <AnimatePresence mode="wait">
              {verifying ? (
                <motion.span key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="inline-flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  Verifying…
                </motion.span>
              ) : (
                <motion.span key="confirm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  Confirm
                </motion.span>
              )}
            </AnimatePresence>
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default VerificationModal;