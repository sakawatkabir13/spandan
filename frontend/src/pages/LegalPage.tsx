import React from 'react';
import { Footer } from '../components/common/Footer';
import { Navbar } from '../components/common/Navbar';

type LegalDocument = 'privacy' | 'terms' | 'medical';

const documents: Record<LegalDocument, { title: string; sections: Array<[string, string]> }> = {
  privacy: {
    title: 'Privacy Policy',
    sections: [
      ['Information we process', 'Spandan processes account details, contact information, doctor credentials, appointment records, queue activity, and the symptoms you choose to submit. Symptoms sent to AI triage are shared with the configured AI provider to generate a specialty recommendation.'],
      ['How information is used', 'We use this information to authenticate users, verify practitioners, operate appointments and queues, provide requested recommendations, prevent abuse, and maintain service reliability.'],
      ['Storage and access', 'Account and appointment access is restricted by role. Symptom submissions are deleted from the active database after 30 days; operational notifications after 90 days. Appointment and payment records are retained for chamber administration. Encrypted recovery backups may retain older records until the backup retention period expires.'],
      ['Your choices', 'Use Account & Chamber Tools to export your data or request deletion. Eligible patient accounts are anonymized after active appointments are resolved. Contact community.cuetinsights@gmail.com for corrections, staff record review, and privacy questions. Do not submit unnecessary identifying or clinical information.'],
      ['AI consent and external services', 'Groq receives the symptoms you submit only when you consent to external processing. Emergency screening runs locally. Configured email, SMS, payment, video, and storage providers receive only the information required for those services.'],
    ],
  },
  terms: {
    title: 'Terms of Service',
    sections: [
      ['Service purpose', 'Spandan helps patients discover verified doctor profiles, request appointment serials, and follow chamber queues. Doctors and assistants are responsible for keeping schedules and queue information accurate.'],
      ['Account responsibilities', 'Provide accurate information, protect your credentials, and use only the permissions assigned to your role. Automated access, harassment, impersonation, and misuse of health or appointment data are prohibited.'],
      ['Availability', 'Appointment times and queue estimates can change because of clinical needs, cancellations, connectivity, or chamber operations. A booking does not guarantee a specific consultation time or medical outcome.'],
      ['Operator contact', 'Spandan support: community.cuetinsights@gmail.com. Contact the operator for account, chamber, payment, and privacy enquiries.'],
      ['Cancellations and payments', 'Patients can cancel eligible appointments or reschedule to an available session with the same doctor. A cancellation does not automatically refund a payment. Ask the chamber to review and record your refund; cash refunds must be returned by the chamber. Online payments and video consultations are available only when enabled by the operator.'],
    ],
  },
  medical: {
    title: 'Medical Disclaimer',
    sections: [
      ['No diagnosis', 'The symptom checker provides preliminary specialty guidance. It does not diagnose illness, prescribe treatment or medication, replace a physical examination, or establish a doctor-patient relationship.'],
      ['Emergencies', 'Do not use Spandan for emergency care. For chest pain, severe breathing difficulty, stroke symptoms, unconsciousness, severe bleeding, seizures, or another emergency, call 999 in Bangladesh or go to the nearest emergency department immediately.'],
      ['Professional judgment', 'Only a licensed clinician can assess your condition. Seek professional care when symptoms persist, worsen, or concern you, even if the tool labels the request routine.'],
      ['AI limitations', 'AI output can be incomplete or wrong. Spandan limits recommendations to a specialty and records the model used, but users and healthcare professionals must apply independent judgment.'],
    ],
  },
};

export const LegalPage: React.FC<{ document: LegalDocument }> = ({ document }) => {
  const content = documents[document];
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-12 sm:px-6">
        <article className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-10 shadow-sm">
          <h1 className="text-3xl font-bold text-slate-900">{content.title}</h1>
          <p className="mt-2 text-sm text-slate-500">Effective 5 October 2026</p>
          <div className="mt-8 space-y-7">
            {content.sections.map(([heading, body]) => (
              <section key={heading}>
                <h2 className="text-lg font-semibold text-slate-900">{heading}</h2>
                <p className="mt-2 text-slate-600 leading-7">{body}</p>
              </section>
            ))}
          </div>
        </article>
      </main>
      <Footer />
    </div>
  );
};
