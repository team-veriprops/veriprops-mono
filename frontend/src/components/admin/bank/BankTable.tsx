"use client";

import { BadgeMinus } from "lucide-react";
import CreateBankDialog from "./CreateBankDialog";
import { Action, Column, DataTable } from "@components/ui/DataTable";
import { QueryBankDto } from "./models";
import { useBankStore } from "./libs/useBankStore";
import { useBankQueries } from "./libs/useBankQueries";
import { getErrorMessage } from "@lib/utils";
import { toast } from "@components/3rdparty/ui/use-toast";

export default function BankTable() {
  const { filters, updateFilters, setCurrentBank, setViewBankDetail } =
    useBankStore();

  const { useSearchBankPage, useDeleteBank } = useBankQueries();
  const { data, isLoading, isError, error } = useSearchBankPage();
  const deleteBank = useDeleteBank()


  const columns: Column<QueryBankDto>[] = [
    {
      key: "name",
      label: "Bank Name",
      sortable: true,
      render: (value, Bank) => <div className="font-medium">{Bank.name}</div>,
    },
    {
      key: "shortName",
      label: "Short Name",
      sortable: true,
      render: (value, Bank) => (
        <div className="text-sm text-muted-foreground">{Bank.shortName}</div>
      ),
    },
    {
      key: "code",
      label: "Code",
      sortable: true,
      render: (value, Bank) => (
        <div className="text-sm text-muted-foreground">{Bank.code}</div>
      ),
    },
    {
      key: "countryCode",
      label: "Country Code",
      sortable: true,
      render: (value, Bank) => (
        <div className="text-sm text-muted-foreground">{Bank.countryCode}</div>
      ),
    },
  ];

  const actions: Action<QueryBankDto>[] = [
    {
      label: "Remove Bank",
      icon: BadgeMinus,
      onClick: (Bank) => {
        handleDeleteBank(Bank)
      },
    },
  ];

  const handleViewDetails = (Bank: QueryBankDto) => {
    setCurrentBank(Bank);
    setViewBankDetail(true);
  };

  const handleDeleteBank = (Bank: QueryBankDto) => {
    deleteBank.mutate(Bank.id ?? "", {
      onSuccess: () => {
        toast({
          title: "Bank deleted",
          description: `${Bank.name} has been deleted successfully.`,
        });
      },
      onError: (error: Error) => {
        const message = getErrorMessage(error, "Failed to delete Bank");

        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
      },
    })
  }

  return (
    <>
      <DataTable
        columns={columns}
        actions={actions}
        dataPage={data!}
        isLoading={isLoading}
        isError={isError}
        error={error}
        currentPage={filters.page!}
        updateFilters={updateFilters}
        isRowClickable={true}
        onRowClick={(Bank) => handleViewDetails(Bank)}
      >
        <CreateBankDialog />
      </DataTable>
    </>
  );
}
