I want to build a web app with the following details:

Product:
	- Name: Veriprops
	- Name explanation: Verified properties
	- Description: A portal that allows people (Nigerians) to verify
	real estate properties (Land/Building). Our target customer
	are Nigerians in the Diaspora.
	- Users:
		1. Admin: administers the platform
		2. Agents: Signs up on the platform to assist in 
		verification process. Agents gets commission for any
		success work done.
			- Types of agents:
				1. Field agent: Physical site inspection
				2. Surveyor: Boundary and location confirmation
				3. Registry agent: Registry search
				4. Lawyer:
					- Title document verification
					- Ownership confirmation
					- Legal opinion
					- Ecumbrances, Fraud and risk assessment
		3. Customers: submits property details for verification.
		Payment is made per verification. The amount paid depends 
		on the verification category (tier).
	- Target Customers: Nigerians in the Diaspora
	- Target Currency: NGN, USD, EUR, GBP
	
Home Page:
	- Hero section
	- The Verification Ecosystem
	- A Rigorous Methodology
	- Verified agents
	- Price
	- Testimonials
	- Call to action
	- Footer:
		- Veriprops: statement of who we're
		- Socials
		- Resources
		- Company

Verification :
	- Description: People submit details or url (of a page on a listing site)
	of the property (land/house) they would want verified.
	- Categories: Basic,Standard, Premium
		1. Basic:
			- Registry search
			- Title document verification
			- Ownership confirmation
		2. Standard:
			- Everything in Basic
			- Physical site inspection
			- Boundary and location confirmation
		3. Premium:
			- Everything in Standard
			- Ecumbrances, Fraud and risk assessment
			- Legal opinion
	- How it works:
		1. Submit Property Details
		2. We Cross-Check Records (including physical inspection)
		3. We Check Eccumberances
		4. We Run Risk Analysis
		5. You Get Your Certified Report
	- Canonical identity for a verification:
		- Verification ID (VERY IMPORTANT)
			- Unique, shareable, public-safe ID
		- Verification certificate system
			- “This property is verified by Veriprops”
		- Public verification lookup
			- Anyone can paste ID → see summary
	- SLA & Time Guarantees
		- Our users care about time certainty.
		- Estimated completion time per tier
		- Countdown / SLA tracker:
			- “Expected in 48 hours”
		- Delay explanation UI
	- Report versioning:
		- v1, v2, v3

- Growth & Conversion Mechanics
	- Referral system:
		- “Invite someone”
		- Share discount with your invitee
	- First-time discount UX
	- Abandoned verification recovery:
		- “You didn’t complete your request”
	
The Strategy:
	- Make “verified property” the default belief.
	- approach:
		1. Enemy: Fraudsters, fake agents, forged documents & uncertainty
		2. Creed: Verify everything, trust nothing blindly
		3. Language: 
			- Trust Score:
				- Weighted (entered by agents, range defined by admin)
				- System (0–100)
				- Clear meaning:
					- 90+ = safe
					- 60–89 = caution
					- 0 - 59 = High risk
				- Consistent display across:
					- Reports
					- etc
			- Verification ID
		4. Playbook: Educate → Build ecosystem → Standardize
		5. Emotion: Protect wealth & family legacy
		6. Symbol: ✅ Veriprops Verified

	- End state: If it’s not verified, nobody buys it.
	
	- Education System (Core to our Strategy)
		- Verification academy / content hub
			- “How land scams work in Nigeria”
			- “How to read a survey plan”
			- ...
		- Embedded education:
			- Tooltips in report:
				- “What is encumbrance?”

		- This builds Ideological power

	
Legal & Liability UX (CRITICAL for your domain):
	- The golden line: “We reduce uncertainty — we do not eliminate it.”
	- We’re operating in real estate + legal interpretation.
	- Terms acceptance per signup and verification
		- “This is an opinion, not a guarantee”
		- Agents are Independent contributors
		- “All communications are recorded for quality and security”
		- Jurisdiction: Nigeria
		- We're not liable to any transaction done outside our platform
	- Consent should be versioned, and user action consent recorded against the consent version.
	- Liability disclaimers in report UI
	- Jurisdiction clarity (Nigeria-specific)
	- Without this, we expose ourself to serious risk.
	- Keep everything Consistent and Defensible legally
	- A surcharge of % if verification cannot continue  (not accessible, Cancled before status becomes IN-PROGRESS)
	- Report footer: “This report represents a professional opinion, not a legal guarantee.”
	- Liability boundaries:
		- We're liable for:
			- Process Integrity:
				- We ensured:
					- Qualified agents were used
					- Required steps were followed per tier
				- Our system:
					- Assigned the right roles
					- Collected required evidence
				- We are liable for: “We followed the defined verification methodology correctly.”
			- Accurate Presentation of Findings:
				- Reports must:
					- Reflect what agents actually submitted
					- Not be altered misleadingly
				- We are liable for: “We did not distort or misrepresent the findings.”
			- Platform Security & Data Handling:
				- Protect:
					- User data
					- Documents
			- Payment Handling
				- If user pays and service is not delivered:
					- Refund obligations apply
		- We're not liable for:
			- Property Authenticity Guarantee
				- Never imply: This property is 100% safe to buy”
				- Instead: “Based on available data and checks performed…”
			- Future Changes or Hidden Issues:
				- We cannot control:
					- Government registry updates
					- Undisclosed disputes
					- Future claims
			- Agent Independent Judgement
				- Agents provide:
					- Observations
					- Opinions
				- Not:
					- Absolute truth
				- We must state: “Findings are based on professional judgement at the time”
			- User Decisions
				- In the case you're a seller, we are NOT responsible for:
					- Whether the user buys or not
					- Financial outcomes
			- Third-party Data Accuracy:
				- We rely on External systems we don’t control: Registry data, documents, etc.
	- Disclaimers:
		- User must acknowledge:
			- Veriprops provides verification services, not guarantees
			- Reports are based on:
				- Data available at the time
			- Final decision rests with the user
		- Show visible disclaimers:
			- Before payment
			- Inside report
	- LIABILITY and REFUND MODEL
		- When We are at fault:
			- Wrong agent assigned
			- Required step skipped

			- Action:
				- Full or partial refund
				- Free re-verification
		- When external issues occur:
			- Registry error
			- Missing records
			- Action:
				- No liability
				- But:
					- Transparent reporting
		- When customer is at fault:
			- Wrong property info
			- Fraudulent submission
			- Action: No refund
			
User Onboarding and Signin:
	- Auth:
		- The various user types signin from a single signin form, the system automatically redirects to either of the following dashboards based on user type (CUSTOMER/ADMIN/AGENT): portal (for customer)/admin ( for admin)/agent (for agent). For an agent that's also a customer, the user is redirected to the agent portal; but allow a switch for the customer portal, verse-versa.
	- Onboarding:
		- Customers starts Onboarding by clicking, "Verify a Property" on the homepage.
			- They are presented the login form, if not already logged in.
			- If they don't have an account yet, they can now create an account by clicking the link on the login form. The system automatically authenticate them.
			- After authentication, the user is now presented with the new verification addition workflow. 
		- Agents starts Onboarding by clicking, "Become an Agent" on the homepage.
			- They are presented the login form, if not already logged in.
			- If they don't have an account yet, they can now create an account by clicking the link on the login form. The system automatically authenticate them.
			- After authentication, the user is now presented with the new agent workflow. 
		- Admin users can only be onboarded in the system through a direct invite from an existing admin with the priviledge.
			- The invitation is sent to the user email, with a link they would click to complete their user onboarding; can choose to authenticate with password or Oauth just like other users
	- Basic User: 
		- CREATE (password - with email OR Oauth)
			- Email (with inline Verify button)
			- Phone (with inline Verify button)
			- First name
			- Last name
			- Country of residence
			- Timezone
			- Preferred currency
		- Login (password - with email and Oauth)
		- Password: Password UX (strength, validation)
		- Forgot password: Full password reset UX
		- Observation: Oauth defers to the backend for 
			init url and token verification.
		- OAuth failure & linking flows:
			- First-time OAuth:
				- Create account
				- Prompt for remaining signup details not yet provided, allow for overrides.
			- Existing user:
				- Ask the user to login with the existing user, and Link the accounts if email matches.
		- Email and Phone verification is compulsory in the start of any signup: verify button on 
			the form input which on click sends verification 
			otp to the user through the backend, and 
			activates a modal where the user enters the otp,
			with a counter and a button for the user to resend the otp.
			Hhone form input is with country flag.
		- Status and state: Error/loading/success states
		- Notifications
		- Security:
			- Connected devices with details and ability to revoke connection:
				- Name
				- Whether it's the current device
				- Browser
				- Location
				- Last active
				- Revoke button, if not the current
				- Allow “Logout from all devices”
			- Linked Oauth accounts with ability to link and unlink:
				- Unlink is only possible when the user is not currently logged with the account.
		- User model should include user_type (USER/ADMIN), an immutable system authority value that cannot change after creation. And user_persona (CUSTOMER|AGENT), a mutable, behavior layer that is a list value; a Customer can also be an Agent.
		- User should be able to resume from where they left off.
		- Allow a user that signup with Oauth to set password, and signin with email/password.
		- Track failed login and OTP failures.
		- A user is deemed trusted as follows: First successful payment for Customer, and first task submission for Agents.

	
	- Customer:
		- Onboarding
			- basic user
		- Property Submission Flow (Needs Depth):
			- Guided multi-step form
			- Location (Google map address input)
			- Property type (land / building)
			- Documents upload
			- Seller info (optional but powerful)
			- Verification tier selection UI
				- Basic / Standard / Premium (On selection, show all it covers)
				- A tier compare button: Clear comparison (what each includes)

			- This is our checkout funnel — it must feel guided, not like a raw form.
		- Pricing Transparency UI
			- Breakdown:
				“Field inspection – ₦X”
				“Legal review – ₦X”
				...
			- Currency switch:
				- NGN / USD / GBP / EUR 
			- Show both local (NGN) and converted currency side-by-side.
			- FX rate transparency:
				- “₦X = $Y (rate: Z)”
			- Locked pricing At checkout time
			- Avoids Why did I pay more than expected?
		- Payment Experience (Critical)
		
			- Currency Selection:
				- NGN / USD / GBP / EUR 
			- Payment method selection:
				Card
				Bank transfer
				International payments
			- Payment status UI:
				Initiated
				Processing
				Succeeded / Failed
			- Retry payment flow
			
		- Verification Tracking Dashboard (CORE)

			- After payment, users need visibility.
			- “My Verifications” dashboard
			- Each request shows:
				- Status (In progress, Completed, etc.)
				- Timeline
				- Assigned agents
				- Example states:
					- Submitted
					- Agents assigned
					- Inspection ongoing
					- Under legal review
					- Completed

			- This is our trust-building engine
		- Timeline & Progress Visualization
			- Not just status — progress storytelling.
			Step-by-step tracker:
			 - Field inspection done
			 - Survey pending
			 - Legal review
			 - etc

			- Think: order tracking (like Amazon/Uber)
		- Evidence & Transparency Layer

			- Customers are remote — they need proof.
			- View:
				- Photos from site
				- Videos
				- Documents
				- Timestamp + location metadata

			- This is what turns Veriprops into “seeing without being there”
		- Final Report Experience (CRITICAL)
			- This is our product output.
			- Structured report UI:
				- fixed schema
				- Summary (green / yellow / red risk)
				- Sections:
					- Physical findings
					- Legal findings
					- Survey results
				- Downloadable PDF
				- “Share report” feature:
					- Who can see what:
						- Full report vs summary
					- Share permissions:
						- Private / public / link-only

				- This must feel like: “A professional audit report, not random notes”
		- Risk & Decision UX (Your Differentiator)
			- This is how users interpret results. And where we build ideological power: “Only buy verified property”
			- Risk indicators:
			- 🟢 Safe
			- 🟡 Caution
			- 🔴 High risk
			- Key flags:
				- Ownership unclear
				- Encumbrances found
			- “Recommended action” section
		- Communication Layer
			- Chat:
				- Per Verification chat
					- Customer <--> Admin <--> Agent
				- General Support Chat
					- Customer <--> Admin
			- Support:
				- Call us
				- FAQs
		- Notification System
			- Customers need real-time awareness.
				- Status change alerts
				- Report ready notification
				- Payment confirmation
			- Channels:
				- In-app notifications
				- Email
		- Revisions / Re-verification Flow
			- Real-world cases aren’t one-shot.
			- Per verification request, enable:
				- “Request re-check”
				- “Upgrade verification tier”
					- Upgrade price from A to B is defined by admin
				- Reuses previous data
		- Location Intelligence UX

			- Many users don’t know Nigerian geography well:
				- Map view of property
				- Nearby landmarks
				- Area insights
		- History & Record Keeping
			- Diaspora users treat this like an investment archive.
			- Past verifications list
			- Download history
			- Re-access reports anytime
		- Account Trust & Security:
			- Email/phone verification status
			- Activity history:
				- “You requested verification on X date”
		
	
	- Agents:
		- Multi-agent Dependency logic:
			- All agents works In parallel
			- Legal opinion comes after all other tasks are done
		- Independent contributors
		- Onboarding
			- basic user
			- Select agent type:
				Field agent / Surveyor / Registry / Lawyer
			- KYC
				- BVN (with verification) or ID Upload(NIN, passport)
				- Selfie verification against BVN Or ID
				- Uploads:
					- Professional license (for lawyers/surveyors)
					- Certifications
		- Approval status dashboard
			- Pending ⏳
			- Approved ✅
			- Rejected ❌ (with reason)
			
		- Dashboard:
			- Assigned jobs
			- Job status tracking
			- Earnings summary
			
		- Job Assignment Flow
			- Job Discovery:
				- Agents see:
					- Jobs available near them (geo-based)
					- Jobs matching their role
					- Jobs are served at first to accept
				- Multi-agent coordination:
					- A single property may require:
						- Field agent
						- Surveyor
						- Lawyer
					- Frontend must show:
						- “You are the Surveyor on this job”
						- Other assigned agents (read-only view)
		- Report Submission System:
			- Each agent type needs a structured submission UI.
				- Field Agent:
					- Property condition checklist
					- Media upload
					- Neighborhood notes
				- Surveyor:
					- Boundary confirmation form
					- Map upload / coordinates
				- Registry Agent:
					- Registry findings
					- Document uploads
				- Lawyer:
					- Legal opinion form
					- Risk flags:
						- Encumbrances
						- Ownership issues
 			- These should NOT be generic forms — they must be role-specific UI flows
			
		- Commission & Earnings System (Very Important)
			- Earnings dashboard
				- Per job
				- Total earnings
			- Payment status:
				- Pending
				- Paid
			- Withdrawal flow:
				- Bank details from store (or new input)
				- Request payout
			- This is what keeps agents engaged.
		- Notification System
			- Agents need real-time awareness.
				- New job alerts
				- Job accepted / reassigned
				- Payment updates
				- Verification feedback from admin
			- Channels:
				- In-app notifications
				- Email
		- Agent Reputation System (HIGH LEVERAGE):
			- For trust + quality control:
			- Ratings from admin/customers
			- Performance metrics:
				- Completion rate
				- Accuracy score
				- Timeliness
			- This becomes our internal power system (relational + ideological)
			
		- Escalation & Issue Reporting
			- “Report issue” button:
				- Property inaccessible
				- Suspicious activity
				- Safety concerns
			- Attach evidence
			
		- Agent Role-Based UX Separation:
			- Different UI per agent type:
				- Lawyer dashboard ≠ Field agent dashboard
			- Conditional rendering:
				- Only show relevant tools
				
		- Location & Coverage Management
			- Agents set:
				- State / city coverage
				- Job matching based on location
		- Trust & Identity Layer (Core to Veriprops)

			- Agents must visibly be “trusted”:
				- “Verified Agent” badge
				- License verification status
				- Years of experience
		- Offline / Low-Connectivity Handling (Nigeria Reality)
			- Save drafts offline
			- Upload retry system
			- Sync indicator
	

	- Admin:
		- Operations Dashboard (Mission Control)
			- A real-time overview of the entire system.
			- Should include:
				- Total active verifications
				- Pending assignments
				- Jobs stuck / delayed
				- Revenue (today / week / month)
				- Agent availability
				- etc
		- Verification Lifecycle Management (CORE)

			- This is our central workflow engine UI, without this, jobs will stall.
			- Admin needs to:
				- View all verification requests
				- See full breakdown:
					- Customer info
					- Property details
					- Uploaded documents
					- Assigned agents
				- Critical actions:
					- Assign agents manually
					- Reassign agents
					- Pause / cancel verification
					- Mark as completed
		- Multi-Agent Coordination View
			- Each property involves multiple roles.
			- A single screen per verification showing:
				- Field agent status
				- Surveyor status
				- Lawyer status
				- Registry agent status
			- Visual:
				- Checklist style:
					- ✅ Field inspection
					- ⏳ Survey pending
					- ❌ Lawyer issue
			- This is our orchestration layer
		- Agent Management System:
			- This protects our platform from bad actors.
			- Agent Approval System:
				- View applications
				- Approve / reject
				- See uploaded credentials
			- Agent Profiles:
				- Performance stats
				- Ratings
				- Past jobs
			- Agent Control Actions
				- Suspend agent
				- Reactivate
				- Limit job access
		- Job Assignment Intelligence
			- Manual assignment alone won’t scale.
			- Suggested agents (based on):
				- Location
				- Availability
				- Performance
			- Load balancing view:
				- Who is overloaded
				- Who is idle
			- Even if backend does logic, frontend must expose it clearly.
		- Report Review & Approval System (CRITICAL)
			- Agents submit reports — but admin must validate before release.
			- Review interface:
				- View all agent submissions in one place
			- Actions:
				- Approve report
				- Request revision
				- Reject submission
			- This is our quality control layer
		- Risk & Fraud Detection UI
			- This is where Veriprops becomes powerful. Helps us prevent fraud slipping through
			- Flagged verifications:
				Suspicious activity
				Conflicting reports
			- Alerts:
				- “Surveyor and field agent disagree”
			- Admin notes system
		- Financial & Commission Management:
			- Payment tracking:
				- Customer payments
				- Agent payouts
				- Commission breakdown per job
			- Payout approval:
				- Approve / hold payments
			- This is our financial control panel
		- Pricing & Tier Configuration
			- Admin UI to:
				- Create/edit tiers
			- Define:
				- Included agent types
				- Pricing per tier
			- Without this, we can’t evolve pricing strategy.
		- System-wide Notification Control
			- Trigger notifications:
				- Assignments
				- Completion
			- Broadcast messages:
				- To all agents
				- To customers
		- Support & Dispute Resolution

			- Real estate = disputes.
			- Ticketing system:
				- Customer complaints
				- Agent issues
			- View conversation history
			- Resolve / escalate cases
		- Geographic Operations View
			- Nigeria is location-sensitive.
			- Map view:
				- Where verifications are happening
			- Regional performance:
				- Lagos vs Abuja vs others
			- Helps our expansion strategy.
		- Analytics & Insights Dashboard
			- Beyond operations.
			- Conversion rate:
				- Signup → payment
			- Average verification time
			- Agent performance trends
			- Revenue by location / tier
			- This drives business decisions
		- Admin Roles & Permissions (IMPORTANT)

			- Not all admins should have full power.
			- Role-based access:
				- Super admin
				- Operations manager
				- Finance admin
			- Permissions:
				- Who can approve payouts?
				- Who can assign agents?
		- Audit Logs & Activity Tracking
			- For accountability; critical for trust + debugging issues.
			- “Who did what” logs:
				- Agent assigned by X
				- Report approved by Y
				- Timestamped actions
		- Content & Trust Layer Management
			- Manage:
				- “How it works” content
				- FAQs
			- Highlight verified agents
			- Manage testimonials

Communication Rules:
	- “For our protection, we shall endeavor to keep all communication within Veriprops”
	- ❌ No direct customer ↔ agent chat
	- ✅ Structured clarification requests
	- ✅ Admin-mediated communication
	- ✅ Full audit logging
	- ❌ No report edits via chat
	- ✅ Formal revision workflow
	- ⚠️ Agent identity visible, contact hidden
	- 🚨 Fraud detection on messages
			

Post MVP:
	- Property Identity Layer
	- Escrow / Transaction Layer
	- Deep Trust & Anti-Fraud Mechanisms