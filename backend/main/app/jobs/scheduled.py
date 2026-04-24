# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from kink import di
#
# from main.app.domain.data.key_value.service import KeyValueService
# from main.app.jobs.tasks.contract_signer_reminder_agent import ContractSignerReminderAgent
#
# contract_signer_reminder_agent: ContractSignerReminderAgent = di[ContractSignerReminderAgent]
# scheduler: AsyncIOScheduler = AsyncIOScheduler()
#
# key_value_service: KeyValueService = di[KeyValueService]
#
# @scheduler.scheduled_job('interval', id='my_job_id', seconds=60)
# async def run_callback_handler():
#     await contract_signer_reminder_agent.remind_all_due_contract_signers()
#     await key_value_service.cleanup_expired()
#     # Renew Drive Subscription
#
#
# def start_scheduler():
#     scheduler.start()
