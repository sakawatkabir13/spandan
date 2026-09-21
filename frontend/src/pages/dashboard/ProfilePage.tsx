import React, { useEffect, useState } from "react";
import { apiClient } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import {
  ApiResponse,
  DoctorProfile,
  PatientProfile,
  Specialization,
  User,
} from "../../types";
import { DashboardLayout } from "../../components/layout/DashboardLayout";
import { LoadingSpinner } from "../../components/common/LoadingSpinner";
import { AssistantManagement } from "../../components/common/AssistantManagement";

export const ProfilePage: React.FC = () => {
  const { user, updateUser, logout } = useAuth();
  const [profile, setProfile] = useState<DoctorProfile | PatientProfile | null>(
    null,
  );
  const [specs, setSpecs] = useState<Specialization[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const isDoctor = user?.role === "doctor";
  useEffect(() => {
    if (!user || !["doctor", "patient"].includes(user.role)) {
      setLoading(false);
      return;
    }
    const load = async () => {
      try {
        const result = await apiClient.get<
          ApiResponse<DoctorProfile | PatientProfile>
        >(isDoctor ? "/doctors/me/profile" : "/patients/me");
        setProfile(result.data.data);
        if (isDoctor) {
          setSelected(
            (result.data.data as DoctorProfile).specializations.map(
              (s) => s.id,
            ),
          );
          setSpecs(
            (
              await apiClient.get<ApiResponse<Specialization[]>>(
                "/doctors/specializations",
              )
            ).data.data,
          );
        }
      } catch {
        setMessage("Unable to load your profile. Please refresh to try again.");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [user?.id, isDoctor]);
  const save = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    const payload = isDoctor
      ? {
          ...fields,
          years_of_experience: Number(fields.years_of_experience),
          specialization_ids: selected,
        }
      : { ...fields, date_of_birth: fields.date_of_birth || null };
    setBusy(true);
    try {
      const result = await apiClient.patch(
        isDoctor ? "/doctors/me/profile" : "/patients/me",
        payload,
      );
      setProfile(result.data.data);
      updateUser(
        (await apiClient.get<ApiResponse<User>>("/auth/me")).data.data,
      );
      setMessage("Profile saved.");
    } catch (error: any) {
      setMessage(
        error.response?.data?.error?.message || "Unable to save profile.",
      );
    } finally {
      setBusy(false);
    }
  };
  const changePassword = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    setBusy(true);
    try {
      await apiClient.post(
        "/auth/change-password",
        Object.fromEntries(new FormData(form)),
      );
      form.reset();
      await logout(false);
    } catch (error: any) {
      setMessage(
        error.response?.data?.error?.message || "Unable to change password.",
      );
    } finally {
      setBusy(false);
    }
  };
  const uploadPhoto = async () => {
    if (!photoFile) return;
    if (photoFile.size > 5 * 1024 * 1024) {
      setMessage("Profile photos must be 5 MB or smaller.");
      return;
    }
    const data = new FormData();
    data.append("photo", photoFile);
    setBusy(true);
    try {
      const result = await apiClient.post(
        isDoctor ? "/doctors/me/profile/photo" : "/patients/me/photo",
        data,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setProfile(result.data.data);
      setPhotoFile(null);
      updateUser(
        (await apiClient.get<ApiResponse<User>>("/auth/me")).data.data,
      );
      setMessage("Profile photo updated.");
    } catch (error: any) {
      setMessage(
        error.response?.data?.error?.message || "Unable to upload profile photo.",
      );
    } finally {
      setBusy(false);
    }
  };
  const doc = isDoctor ? (profile as DoctorProfile | null) : null;
  const patient = !isDoctor ? (profile as PatientProfile | null) : null;
  const relativePhotoUrl = profile?.profile_photo_url;
  const mediaBase = (apiClient.defaults?.baseURL || window.location.origin).replace(
    /\/api\/v1\/?$/,
    "",
  );
  const photoUrl = relativePhotoUrl
    ? relativePhotoUrl.startsWith("http")
      ? relativePhotoUrl
      : `${mediaBase}${relativePhotoUrl}`
    : null;
  return (
    <DashboardLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <section className="glass-card p-6 space-y-4">
          <h1 className="text-2xl font-bold">My Profile</h1>
          <p className="text-slate-600">
            {user?.email} · {user?.phone_number}
          </p>
          {message && (
            <p role="status" className="text-spandan-800">
              {message}
            </p>
          )}
          {loading ? (
            <LoadingSpinner />
          ) : (
            profile && (
              <form onSubmit={save} className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-xl border border-slate-200 p-4">
                  {photoUrl ? (
                    <img
                      src={photoUrl}
                      alt={`${profile.full_name} profile`}
                      className="h-20 w-20 rounded-full object-cover border border-slate-200"
                    />
                  ) : (
                    <div className="h-20 w-20 rounded-full bg-spandan-100 text-spandan-800 flex items-center justify-center text-2xl font-bold">
                      {profile.full_name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="space-y-2 flex-1">
                    <label className="block text-sm font-medium">
                      Profile photo
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="block mt-1 text-sm w-full"
                        onChange={(event) =>
                          setPhotoFile(event.target.files?.[0] || null)
                        }
                      />
                    </label>
                    <p className="text-xs text-slate-500">JPEG, PNG, or WebP up to 5 MB.</p>
                    <button
                      type="button"
                      disabled={busy || !photoFile}
                      onClick={uploadPhoto}
                      className="btn-secondary text-sm py-2"
                    >
                      Upload Photo
                    </button>
                  </div>
                </div>
                <label className="block text-sm">
                  Full name
                  <input
                    name="full_name"
                    required
                    minLength={2}
                    defaultValue={profile.full_name}
                    className="input-field"
                  />
                </label>
                {doc ? (
                  <>
                    <p className="rounded-xl bg-slate-100 p-4 text-sm">
                      BMDC: {doc.medical_registration_number} · Status:{" "}
                      <strong>{doc.verification_status}</strong>
                      {doc.verification_notes && (
                        <span className="block mt-2">
                          {doc.verification_notes}
                        </span>
                      )}
                    </p>
                    <label className="block text-sm">
                      Current workplace
                      <input
                        name="current_workplace"
                        defaultValue={doc.current_workplace || ""}
                        className="input-field"
                      />
                    </label>
                    <label className="block text-sm">
                      Years of experience
                      <input
                        name="years_of_experience"
                        type="number"
                        min={0}
                        required
                        defaultValue={doc.years_of_experience}
                        className="input-field"
                      />
                    </label>
                    <label className="block text-sm">
                      Biography
                      <textarea
                        name="biography"
                        rows={4}
                        defaultValue={doc.biography || ""}
                        className="input-field"
                      />
                    </label>
                    <fieldset>
                      <legend className="text-sm font-semibold mb-2">
                        Specializations
                      </legend>
                      <div className="grid sm:grid-cols-2 gap-2">
                        {specs.map((spec) => (
                          <label
                            key={spec.id}
                            className="text-sm flex items-center gap-2"
                          >
                            <input
                              type="checkbox"
                              checked={selected.includes(spec.id)}
                              onChange={(e) =>
                                setSelected((all) =>
                                  e.target.checked
                                    ? [...all, spec.id]
                                    : all.filter((id) => id !== spec.id),
                                )
                              }
                            />
                            {spec.name}
                          </label>
                        ))}
                      </div>
                    </fieldset>
                  </>
                ) : (
                  patient && (
                    <>
                      <label className="block text-sm">
                        Date of birth
                        <input
                          name="date_of_birth"
                          type="date"
                          defaultValue={patient.date_of_birth || ""}
                          className="input-field"
                        />
                      </label>
                      <label className="block text-sm">
                        Gender
                        <select
                          name="gender"
                          defaultValue={patient.gender || ""}
                          className="input-field"
                        >
                          <option value="">Prefer not to say</option>
                          <option>Male</option>
                          <option>Female</option>
                          <option>Other</option>
                        </select>
                      </label>
                      <label className="block text-sm">
                        Address
                        <textarea
                          name="address"
                          defaultValue={patient.address || ""}
                          className="input-field"
                        />
                      </label>
                      <label className="block text-sm">
                        Emergency contact
                        <input
                          name="emergency_contact"
                          defaultValue={patient.emergency_contact || ""}
                          className="input-field"
                        />
                      </label>
                    </>
                  )
                )}
                <button disabled={busy} className="btn-primary">
                  Save Profile
                </button>
              </form>
            )
          )}
        </section>
        <section className="glass-card p-6 space-y-4">
          <h2 className="text-xl font-bold">Change Password</h2>
          <p className="text-sm text-slate-600">
            You will need to sign in again on all devices after changing your
            password.
          </p>
          <form onSubmit={changePassword} className="space-y-3">
            <label className="block text-sm">
              Current password
              <input
                type="password"
                name="current_password"
                autoComplete="current-password"
                required
                className="input-field"
              />
            </label>
            <label className="block text-sm">
              New password
              <input
                type="password"
                name="new_password"
                autoComplete="new-password"
                minLength={8}
                required
                className="input-field"
              />
            </label>
            <button disabled={busy} className="btn-primary">
              Change Password
            </button>
          </form>
        </section>
        {doc && <AssistantManagement doctorId={doc.id} />}
      </div>
    </DashboardLayout>
  );
};
