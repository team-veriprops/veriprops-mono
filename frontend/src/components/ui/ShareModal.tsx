import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@3rdparty/ui/dialog";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Textarea } from "@3rdparty/ui/textarea";
import { Label } from "@3rdparty/ui/label";
import { Plus, X, Copy, Mail } from "lucide-react";

const FacebookIcon = () => (
  <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
  </svg>
);
import { toast } from "sonner";
import { copyToClipboard } from "@lib/utils";
import { useUIStore } from "./libs/useUiStore";

interface ShareReferralModalProps {
  defaultMessage: string;
  extLink: string;
}

export default function ShareModal({ defaultMessage, extLink}: ShareReferralModalProps) {
  const {isShareModalOpen, setShareModalOpen} = useUIStore()
  const [emails, setEmails] = useState<string[]>([""]);
  const [message, setMessage] = useState(defaultMessage);
  const [isSending, setIsSending] = useState(false);

  const addEmailField = () => {
    if (emails.length < 10) {
      setEmails([...emails, ""]);
    }
  };

  const removeEmailField = (index: number) => {
    setEmails(emails.filter((_, i) => i !== index));
  };

  const updateEmail = (index: number, value: string) => {
    const newEmails = [...emails];
    newEmails[index] = value;
    setEmails(newEmails);
  };

  const validateEmails = () => {
    const validEmails = emails.filter(e => e.trim() !== "");
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return validEmails.every(e => emailRegex.test(e));
  };

  const handleSend = async () => {
    const validEmails = emails.filter(e => e.trim() !== "");
    
    if (validEmails.length === 0) {
      toast.error("Please add at least one email address");
      return;
    }

    if (!validateEmails()) {
      toast.error("Please enter valid email addresses");
      return;
    }

    if (message.length > 250) {
      toast.error("Message must be 250 characters or less");
      return;
    }

    setIsSending(true);
    try {
      toast.success(`Referral shared with ${validEmails.length} ${validEmails.length === 1 ? 'person' : 'people'}!`);
      setShareModalOpen(false);
      setEmails([""]);
      setMessage("");
    } catch (error) {
      toast.error("Failed to share referral");
    } finally {
      setIsSending(false);
    }
  };

  const handleCopyLink = async () => {
    try {
      await copyToClipboard(extLink);
      toast.success("Link copied to clipboard!");
    } catch (error) {
      toast.error("Failed to copy link");
    }
  };

  const handleEmailClient = () => {
    const subject = encodeURIComponent("Join Veriprops Trust Network");
    const body = encodeURIComponent(`${message}\n\n${extLink}`);
    window.open(`mailto:?subject=${subject}&body=${body}`);
    toast.success("Opening email client...");
  };

  const handleFacebookShare = () => {
    const url = encodeURIComponent(extLink);
    window.open(`https://www.facebook.com/sharer/sharer.php?u=${url}`, '_blank');
  };

  return (
    <Dialog open={isShareModalOpen} onOpenChange={setShareModalOpen}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Share Referral Link</DialogTitle>
          <DialogDescription>
            Invite trusted people to join Veriprops
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Email inputs */}
          <div>
            <Label htmlFor="emails">Email addresses</Label>
            <div className="space-y-2 mt-2">
              {emails.map((email, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    value={email}
                    onChange={(e) => updateEmail(index, e.target.value)}
                    placeholder="email@example.com"
                    type="email"
                  />
                  {emails.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeEmailField(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
              {emails.length < 10 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addEmailField}
                  className="w-full"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add another email
                </Button>
              )}
            </div>
          </div>

          {/* Message */}
          <div>
            <Label htmlFor="message">Message (optional)</Label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Add a personal message..."
              maxLength={250}
              className="mt-2"
              rows={3}
            />
            <p className="text-xs text-muted-foreground mt-1">
              {message.length}/250 characters
            </p>
          </div>

          {/* Send button */}
          <Button 
            onClick={handleSend} 
            disabled={isSending}
            className="w-full bg-destructive hover:bg-destructive/90"
          >
            {isSending ? "Sending..." : "Send"}
          </Button>

          {/* Share options */}
          <div className="flex items-center justify-between pt-4 border-t border-border">
            <Button variant="ghost" size="sm" onClick={handleCopyLink}>
              <Copy className="h-4 w-4 mr-2" />
              Copy link
            </Button>
            <Button variant="ghost" size="sm" onClick={handleEmailClient}>
              <Mail className="h-4 w-4 mr-2" />
              Email
            </Button>
            <Button variant="ghost" size="sm" onClick={handleFacebookShare}>
              <FacebookIcon />
              Facebook
            </Button>
            <Button variant="ghost" size="sm" onClick={setShareModalOpen.bind(null, false)}>
              Cancel
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
