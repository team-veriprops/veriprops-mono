/**
 * UAT — server-driven admin lists (CLAUDE.md "Pagination Convention").
 *
 * Every admin DataTable sorts, pages and sizes its pages on the server: a header is offered as
 * sortable only when the backend lists it in `meta.sortableFields`, the rows render in exactly
 * the order the backend returned, and Next / Previous / rows-per-page all go back to it.
 */
import { Page, Response } from "@playwright/test";

import { datatableSortTestId, DATATABLE_TEST_IDS } from "@components/ui/table/testIds";
import { ROUTES } from "@lib/routes";

import { expect, test } from "../fixtures";
import { goto } from "../helpers/app";

const USERS_API = "/api/users/admins/users?";

type UsersPage = {
  items: { id: string; email: string }[];
  meta: { page: number; pageSize: number; totalPages: number; sort?: string; sortableFields?: string[] };
};

/** Run *action* and return the users-list page the backend answered it with. */
async function usersPageAfter(page: Page, action: () => Promise<unknown>): Promise<UsersPage> {
  const [response] = await Promise.all([
    page.waitForResponse((r: Response) => r.url().includes(USERS_API) && r.request().method() === "GET" && r.ok()),
    action(),
  ]);
  return (await response.json()).data as UsersPage;
}

/** The row ids the table renders, top to bottom. */
async function renderedRowIds(page: Page): Promise<string[]> {
  return page.getByTestId(DATATABLE_TEST_IDS.ROW).evaluateAll((rows) => rows.map((r) => r.getAttribute("data-row-id") ?? ""));
}

test.describe("UAT-LIST — server-driven admin lists @P1", () => {
  test("UAT-LIST-01 · the users list sorts, pages and sizes on the server", async ({ adminPage: page }) => {
    const first = await usersPageAfter(page, () => goto(page, ROUTES.ADMIN.USERS));
    expect(first.meta.sort).toBe("dateCreated desc");
    expect(first.meta.sortableFields).toContain("email");

    // Only the backend's sortable columns are offered; "Name" is not one of them.
    const emailHeader = page.getByTestId(datatableSortTestId("email"));
    await expect(emailHeader).toHaveAttribute("aria-sort", "none");
    await expect(page.getByTestId(datatableSortTestId("name"))).toHaveCount(0);

    // Sorting asks the backend, and the table shows its rows in exactly that order.
    const ascending = await usersPageAfter(page, () => emailHeader.click());
    expect(ascending.meta.sort).toBe("email asc");
    await expect(page).toHaveURL(/orderBy=email(\+|%20)asc/);
    await expect(emailHeader).toHaveAttribute("aria-sort", "ascending");
    await expect.poll(() => renderedRowIds(page)).toEqual(ascending.items.map((u) => u.id));

    const descending = await usersPageAfter(page, () => emailHeader.click());
    expect(descending.meta.sort).toBe("email desc");
    await expect(emailHeader).toHaveAttribute("aria-sort", "descending");
    await expect.poll(() => renderedRowIds(page)).toEqual(descending.items.map((u) => u.id));

    // Five rows a page: the size goes to the backend, and paging resets to the first page.
    const small = await usersPageAfter(page, async () => {
      await page.getByRole("combobox", { name: "Rows per page" }).click();
      await page.getByRole("option", { name: "5", exact: true }).click();
    });
    expect(small.meta.pageSize).toBe(5);
    expect(small.meta.page).toBe(0);
    expect(small.meta.sort).toBe("email desc");
    await expect(page.getByTestId(DATATABLE_TEST_IDS.ROW)).toHaveCount(small.items.length);
    expect(small.items.length).toBeLessThanOrEqual(5);
    await expect(page.getByTestId(DATATABLE_TEST_IDS.LABEL)).toHaveText(`Page 1 of ${Math.max(small.meta.totalPages, 1)}`);

    test.skip(small.meta.totalPages < 2, "fewer than six users — nothing to page through");

    // Next keeps the sort and the size; Previous comes back to the same first page.
    const second = await usersPageAfter(page, () => page.getByTestId(DATATABLE_TEST_IDS.NEXT).click());
    expect([second.meta.page, second.meta.pageSize, second.meta.sort]).toEqual([1, 5, "email desc"]);
    await expect(page.getByTestId(DATATABLE_TEST_IDS.LABEL)).toHaveText(`Page 2 of ${second.meta.totalPages}`);
    await expect.poll(() => renderedRowIds(page)).toEqual(second.items.map((u) => u.id));

    // Other specs add users in parallel, so the first page is compared with what the backend
    // returns now, not with the earlier read.
    const back = await usersPageAfter(page, () => page.getByTestId(DATATABLE_TEST_IDS.PREV).click());
    expect([back.meta.page, back.meta.sort]).toEqual([0, "email desc"]);
    await expect.poll(() => renderedRowIds(page)).toEqual(back.items.map((u) => u.id));
  });
});
