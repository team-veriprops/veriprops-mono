"use client";

import { useEffect, useState } from "react";
import { Button } from "@3rdparty/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@3rdparty/ui/dialog";
import { Input } from "@3rdparty/ui/input";
import { Plus, Settings } from "lucide-react";

import { CreateBankDto} from "./models";
import { useBankQueries } from "./libs/useBankQueries";
import { useBankStore } from "./libs/useBankStore";

import { useForm, FormProvider, Controller } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { toast } from "@3rdparty/ui/use-toast";
import { getErrorMessage } from "@lib/utils";
import { FormField } from "@components/ui/form/FormField";

const BankSchema = z.object({
  name: z.string().min(1, "Bank name is required"),
  shortName: z.string().min(1, "Bank short name is required"),
  code: z.string().min(1, "Bank code is required"),
  countryCode: z.string().min(1, "Bank country code is required"),
});

type BankFormValues = z.infer<typeof BankSchema>;

export default function CreateBankDialog() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const Bank_page_size = 100;

  const { updateFilters } = useBankStore();
  const { useSearchBankPage, useCreateBank } = useBankQueries();

  const { data: dataPage, isLoading, isError } = useSearchBankPage();

  useEffect(() => {
    updateFilters({ pageSize: Bank_page_size });
  }, [Bank_page_size, updateFilters]);

  const createBank = useCreateBank();

  const methods = useForm<BankFormValues>({
    resolver: zodResolver(BankSchema),
    defaultValues: {
      name: "",
      shortName: "",
      code: "",
      countryCode: ""
    },
  });

  const {
    handleSubmit,
    reset,
    control,
    formState: { isSubmitting },
  } = methods;

  const onSubmit = (data: BankFormValues) => {
    setApiError(null);

    const payload: CreateBankDto = {
      name: data.name,
      shortName: data.shortName,
      code: data.code,
      countryCode: data.countryCode
    };

    createBank.mutate(payload, {
      onSuccess: () => {
        reset();
        setIsModalOpen(false);

        toast({
          title: "Bank created",
          description: `${data.name} has been created successfully.`,
        });
      },
      onError: (error: Error) => {
        const message = getErrorMessage(error, "Failed to create Bank");
        setApiError(message);

        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
      },
    });
  };

  return (
    <Dialog
      open={isModalOpen}
      onOpenChange={(open) => {
        setIsModalOpen(open);
        if (!open) {
          reset();
          setApiError(null);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="h-4 w-4 mr-2" />
          Create Bank
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Bank</DialogTitle>
          <DialogDescription>
            Create a custom Bank and assign system permissions to it.
          </DialogDescription>
        </DialogHeader>

        <FormProvider {...methods}>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Name */}
            <FormField name="name" label="Bank Name">
              <Input placeholder="e.g. First Bank Plc" autoFocus />
            </FormField>

            {/* shortName */}
            <FormField name="shortName" label="Short Name">
              <Input placeholder="e.g. FBank" />
            </FormField>

            {/* code */}
            <FormField name="countryCode" label="Code">
              <Input placeholder="e.g. 003" />
            </FormField>

            {/* countryCode */}
            <FormField name="countryCode" label="Country Code">
              <Input placeholder="e.g. NG" />
            </FormField>

            {/* API Error */}
            {apiError && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                {apiError}
              </div>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsModalOpen(false)}
              >
                Cancel
              </Button>

              <Button
                type="submit"
                disabled={isSubmitting || isLoading}
              >
                <Settings className="h-4 w-4 mr-2" />
                {isSubmitting ? "Creating..." : "Create Bank"}
              </Button>
            </DialogFooter>
          </form>
        </FormProvider>
      </DialogContent>
    </Dialog>
  );
}
