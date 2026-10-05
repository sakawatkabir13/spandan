import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

const bengali: Record<string, string> = {
  'Find doctors across Bangladesh': 'বাংলাদেশ জুড়ে ডাক্তার খুঁজুন',
  'Public hospital directory': 'হাসপাতালের প্রকাশিত ডাক্তার তালিকা', 'Book on Spandan': 'স্পন্দনে বুক করুন',
  'Doctor directory options': 'ডাক্তার তালিকার ধরন', 'Public hospital listing': 'হাসপাতালের প্রকাশিত তথ্য',
  'Contact hospital': 'হাসপাতালে যোগাযোগ করুন', 'Division': 'বিভাগ', 'All divisions': 'সব বিভাগ',
  'All districts': 'সব জেলা', 'Specialty': 'বিশেষজ্ঞ বিভাগ', 'All specialties': 'সব বিশেষজ্ঞ বিভাগ',
  'Doctor, specialty or hospital': 'ডাক্তার, বিশেষজ্ঞ বিভাগ বা হাসপাতাল',
  'View hospital listing': 'হাসপাতালের তথ্য দেখুন', 'Call hospital': 'হাসপাতালে ফোন করুন',
  'Visit hospital website': 'হাসপাতালের ওয়েবসাইট দেখুন', 'Official hospital source': 'হাসপাতালের মূল তথ্যসূত্র',
  'Source reviewed': 'তথ্যসূত্র পর্যালোচনার তারিখ', 'Page': 'পৃষ্ঠা', 'Retry': 'আবার চেষ্টা করুন',
  'Reset filters': 'বাছাই মুছুন', 'Loading hospital listings...': 'হাসপাতালের তালিকা আসছে...',
  'public hospital listings': 'টি হাসপাতালের প্রকাশিত তালিকা', 'Directory results pages': 'তালিকার ফলাফলের পৃষ্ঠা',
  'Back to hospital directory': 'হাসপাতালের তালিকায় ফিরে যান', 'Consultation fee': 'পরামর্শ ফি',
  'Qualifications published by hospital': 'হাসপাতাল কর্তৃক প্রকাশিত যোগ্যতা', 'Hospital or chamber': 'হাসপাতাল বা চেম্বার',
  'Published consultation hours': 'প্রকাশিত রোগী দেখার সময়',
  'This is not a confirmation from the doctor.': 'এটি ডাক্তারের পক্ষ থেকে নিশ্চিত করা তথ্য নয়।',
  'To request a correction or removal, contact': 'তথ্য সংশোধন বা অপসারণের জন্য যোগাযোগ করুন',
  'Confirm current fees directly with the hospital.': 'বর্তমান ফি সরাসরি হাসপাতালে নিশ্চিত করুন।',
  'Hours are not reliably published. Contact the hospital.': 'নির্ভরযোগ্য সময়সূচী প্রকাশিত নেই। হাসপাতালে যোগাযোগ করুন।',
  'Published hours may have changed. They do not reserve an appointment or show live availability.': 'প্রকাশিত সময়সূচী বদলে যেতে পারে। এটি অ্যাপয়েন্টমেন্ট সংরক্ষণ বা বর্তমান খালি সময় নির্দেশ করে না।',
  'No public listings match your search. Try another division or specialty.': 'আপনার অনুসন্ধানের সঙ্গে কোনো প্রকাশিত তালিকা মেলেনি। অন্য বিভাগ বা বিশেষজ্ঞ বিভাগ চেষ্টা করুন।',
  'Explore an initial directory covering all eight divisions, sourced from official hospital websites. This is not a complete national register.': 'হাসপাতালের মূল ওয়েবসাইট থেকে সংগৃহীত আট বিভাগের প্রাথমিক তালিকা দেখুন। এটি দেশের সব ডাক্তারের পূর্ণ তালিকা নয়।',

  'District': 'জেলা', 'Maximum fee (৳)': 'সর্বোচ্চ ফি (৳)', 'Available on': 'যে তারিখে ডাক্তার দেখাবেন', 'Filter Results': 'ফলাফল বাছাই করুন',
  'View Chambers & Book': 'চেম্বার দেখুন ও বুক করুন', 'My Appointments & Live Serials': 'আমার অ্যাপয়েন্টমেন্ট ও লাইভ সিরিয়াল', 'Refresh Serials': 'সিরিয়াল হালনাগাদ করুন',
  'Book Serial': 'সিরিয়াল বুক করুন', 'Confirm & Get Serial Number': 'নিশ্চিত করে সিরিয়াল নিন', 'Booking Confirmed!': 'বুকিং নিশ্চিত হয়েছে!',
  'Confirm attendance': 'উপস্থিতি নিশ্চিত করুন', 'Cancel Serial': 'সিরিয়াল বাতিল করুন', 'Yes, Cancel Serial': 'হ্যাঁ, সিরিয়াল বাতিল করুন', 'Keep Appointment': 'অ্যাপয়েন্টমেন্ট রাখুন',
  'Forgot your password?': 'পাসওয়ার্ড ভুলে গেছেন?', 'Sign In': 'প্রবেশ করুন', 'Signing in...': 'প্রবেশ করা হচ্ছে...',
  'Find Doctors': 'ডাক্তার খুঁজুন', 'AI Symptom Checker': 'এআই উপসর্গ যাচাই',
  'Login': 'প্রবেশ করুন', 'Register': 'নিবন্ধন করুন', 'Logout': 'সাইন আউট', 'Dashboard': 'ড্যাশবোর্ড',
  'Create your Spandan account': 'আপনার স্পন্দন অ্যাকাউন্ট তৈরি করুন',
  'Choose your account type below to get started': 'শুরু করতে অ্যাকাউন্টের ধরন বেছে নিন',
  'Patient Account': 'রোগীর অ্যাকাউন্ট', 'Doctor Practitioner': 'ডাক্তারের অ্যাকাউন্ট',
  'Full Name': 'পূর্ণ নাম', 'Email Address': 'ইমেইল ঠিকানা', 'Phone Number': 'ফোন নম্বর', 'Password': 'পাসওয়ার্ড',
  'Sign in': 'প্রবেশ করুন', 'Forgot password?': 'পাসওয়ার্ড ভুলে গেছেন?', 'Welcome back to Spandan': 'স্পন্দনে স্বাগতম',
  'Register as Patient': 'রোগী হিসেবে নিবন্ধন', 'Register as Doctor': 'ডাক্তার হিসেবে নিবন্ধন', 'Creating account...': 'অ্যাকাউন্ট তৈরি হচ্ছে...',
  'Book demo appointment': 'ডেমো অ্যাপয়েন্টমেন্ট বুক করুন',
  'Academic demo account': 'শিক্ষামূলক ডেমো অ্যাকাউন্ট',
  'Academic demo: appointment slots, queues and fees are simulated. No real medical consultation or payment is arranged.': 'শিক্ষামূলক ডেমো: সময়সূচী, সিরিয়াল ও ফি অনুকরণ করা হয়েছে। এখানে বাস্তব চিকিৎসা বা অর্থ লেনদেন হয় না।',
  'These are public hospital listings. Spandan has not independently verified these doctors or confirmed their availability. Contact the hospital to confirm fees, hours and appointments. Real appointments must be confirmed with the hospital. Where available, Spandan offers separately labelled simulated bookings for academic demonstration.': 'এগুলো হাসপাতালের প্রকাশিত তথ্য। বাস্তব ফি, সময়সূচী ও চিকিৎসার জন্য হাসপাতালে যোগাযোগ করুন। স্পন্দনের শিক্ষামূলক ডেমো বুকিং আলাদাভাবে চিহ্নিত এবং বাস্তব অ্যাপয়েন্টমেন্ট নয়।',
  'This profile has an academic demo account with simulated fees and availability. It does not book a real hospital visit.': 'এই প্রোফাইলের ডেমো অ্যাকাউন্টে সময়সূচী ও ফি অনুকরণ করা হয়েছে। এর মাধ্যমে বাস্তব হাসপাতালে চিকিৎসার বুকিং হয় না।',
  'Find Verified Doctor Chambers': 'যাচাইকৃত ডাক্তারের চেম্বার খুঁজুন', 'Search': 'খুঁজুন', 'All Specializations': 'সব বিশেষজ্ঞ',
  'Previous': 'আগের', 'Next': 'পরের', 'Book Appointment': 'অ্যাপয়েন্টমেন্ট বুক করুন', 'Confirm Booking': 'বুকিং নিশ্চিত করুন',
  'Booking for': 'যার জন্য বুকিং', 'Myself': 'নিজের জন্য', 'Consultation': 'পরামর্শ', 'At the chamber': 'চেম্বারে',
  'Appointment History': 'অ্যাপয়েন্টমেন্টের ইতিহাস', 'Cancel': 'বাতিল', 'Reschedule visit': 'সময় পরিবর্তন',
  'Payment & receipt': 'পেমেন্ট ও রসিদ', 'notifications': 'বিজ্ঞপ্তি', 'security': 'নিরাপত্তা', 'privacy': 'গোপনীয়তা',
  'family': 'পরিবার', 'waitlist': 'অপেক্ষার তালিকা', 'billing': 'বিল', 'calendar': 'ক্যালেন্ডার', 'analytics': 'পরিসংখ্যান',
  'Account & Chamber Tools': 'অ্যাকাউন্ট ও চেম্বারের সরঞ্জাম', 'Family members': 'পরিবারের সদস্য', 'Add family member': 'পরিবারের সদস্য যোগ করুন',
};
const LanguageContext = createContext({ language: 'en', setLanguage: (_value: string) => {}, t: (value: string) => value });
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState(() => localStorage.getItem('spandan_language') === 'bn' ? 'bn' : 'en');
  useEffect(() => { localStorage.setItem('spandan_language', language); document.documentElement.lang = language; }, [language]);
  return <LanguageContext.Provider value={{ language, setLanguage, t: value => language === 'bn' ? (bengali[value] || value) : value }}>{children}</LanguageContext.Provider>;
}
export const useLanguage = () => useContext(LanguageContext);
