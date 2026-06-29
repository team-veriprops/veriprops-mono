import { useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Autocomplete } from "@react-google-maps/api";
import { ExactLocation } from "@/types/models";
import { addressSchema, type AddressFormValues } from "./schemas";

/* ------------------------------------------------------------------
   Local minimal Google type (avoids library conflicts)
------------------------------------------------------------------- */

type GoogleAddressComponent = {
  long_name: string;
  short_name: string;
  types: string[];
};

/* ------------------------------------------------------------------
   Constants
------------------------------------------------------------------- */

const initialValues: AddressFormValues = {
  address: "",
  country: "Nigeria",
  state: "",
  lga: "",
  city: "",
  area: "",
  street: "",
  streetNumber: "",
  postalCode: "",
  latitude: "",
  longitude: "",
  placeId: "",
};

/* ------------------------------------------------------------------ */
/* Props */
/* ------------------------------------------------------------------ */

type AddressSearchFormProps =  {
  onChange: (address: ExactLocation | undefined) => void
}


/* ------------------------------------------------------------------
   Component
------------------------------------------------------------------- */


export default function AddressSearchForm({onChange}:AddressSearchFormProps) {
  const {
    register,
    reset,
    formState: { errors },
  } = useForm<AddressFormValues>({
    resolver: zodResolver(addressSchema),
    defaultValues: initialValues,
  });

  const autocompleteRef =
    useRef<google.maps.places.Autocomplete | null>(null);

  /* ------------------------------------------------------------------
     Helpers
  ------------------------------------------------------------------- */

  const extract = (
    components: GoogleAddressComponent[],
    types: string[]
  ): string =>
    components.find(c => types.some(t => c.types.includes(t)))
      ?.long_name ?? "";

  const resetAll = (address = "") => {
    reset({ ...initialValues, address });
    onChange(undefined);
  };

  const onPlaceChanged = () => {
    if (!autocompleteRef.current) return;

    const place = autocompleteRef.current.getPlace();
    if (!place.address_components || !place.geometry) return;

    const components =
      place.address_components as GoogleAddressComponent[];

    const values: AddressFormValues = {
      address: place.formatted_address || "",
      country: extract(components, ["country"]),
      state: extract(components, ["administrative_area_level_1"]),
      lga: extract(components, ["administrative_area_level_2"]),
      city:
        extract(components, ["locality"]) ||
        extract(components, ["administrative_area_level_3"]),
      area: extract(components, [
        "sublocality",
        "sublocality_level_1",
        "neighborhood",
      ]),
      street: extract(components, ["route"]),
      streetNumber: extract(components, ["street_number"]),
      postalCode: extract(components, ["postal_code"]),
      latitude: place?.geometry?.location?.lat().toString() ?? "",
      longitude: place?.geometry?.location?.lng().toString() ?? "",
      placeId: place.place_id || "",
    };

    reset(values);

    /* Emit FINAL normalized address */
    onChange({
      address: values.address,
      country: values.country,
      state: values.state,
      lga: values.lga ?? "",
      city: values.city ?? "",
      area: values.area ?? "",
      street: values.street ?? "",
      streetNumber: values.streetNumber ?? "",
      postalCode: values.postalCode ?? "",
      coordinates: { lat: Number(values.latitude), lng: Number(values.longitude) },
      placeId: values.placeId,
    });
  };

  /* ------------------------------------------------------------------
     Render
  ------------------------------------------------------------------- */

  return (
      <div className="space-y-2 max-w-md">
        {/* Address search */}
        <Autocomplete
          onLoad={ref => (autocompleteRef.current = ref)}
          onPlaceChanged={onPlaceChanged}
          options={{
            componentRestrictions: { country: "ng" },
            fields: [
              "address_components",
              "geometry.location",
              "formatted_address",
              "place_id",
            ],
          }}
        >
          <input
            {...register("address")}
            onChange={e => resetAll(e.target.value)}
            placeholder="Search property address"
            className="w-full border p-2 rounded"
          />
        </Autocomplete>

        {errors.address && (
          <p className="text-sm text-red-500">
            {errors.address.message}
          </p>
        )}

        {/* Auto-filled (disabled) fields */}
        <label>Country:
        <input {...register("country")} disabled />
        </label>
        <label>State:
        <input {...register("state")} disabled />
        </label>
        <label> LGA:
        <input {...register("lga")} disabled />
        </label>
        <label> City:
        <input {...register("city")} disabled />
        </label>
        <label> Area:
        <input {...register("area")} disabled />
        <input {...register("streetNumber")} disabled />
        <input {...register("street")} disabled />
        </label>
        <label> Postal code:
        <input {...register("postalCode")} disabled />
        </label>

        <div className="flex gap-2">
          <input {...register("latitude")} disabled />
          <input {...register("longitude")} disabled />
        </div>
      </div>
  );
}
